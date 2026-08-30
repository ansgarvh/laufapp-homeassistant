from pathlib import Path
import json, subprocess, yaml
ROOT=Path(__file__).resolve().parents[1]

def test_versions_and_assets():
    cfg=yaml.safe_load((ROOT/'laufapp/config.yaml').read_text())
    assert cfg['version']=='0.2.6'
    assert 'APP_VERSION = "0.2.6"' in (ROOT/'laufapp/app/main_v026.py').read_text()
    assert 'ARG BUILD_VERSION=0.2.6' in (ROOT/'laufapp/Dockerfile').read_text()
    assert 'main_v026:app' in (ROOT/'laufapp/run.sh').read_text()
    static=ROOT/'laufapp/app/static'
    for name in ['index.html','styles.css','bugfix.css','app.js','manifest.webmanifest','sw.js','icon-192.png','icon-512.png','assets/bugfix.css','assets/v020.js','assets/v020.css','assets/v020_science.js','assets/v020_science.css','assets/v023_aggressiveness.js','assets/v025.js','assets/v025.css']:assert (static/name).exists()
    m=json.loads((static/'manifest.webmanifest').read_text());assert m['display']=='standalone'
    sw=(static/'sw.js').read_text()
    assert "const CACHE='laufapp-v0.2.5'" in sw
    index=(static/'index.html').read_text()
    for asset in ['app.js?v=0.2.5','assets/bugfix.css?v=0.2.5','assets/v020.js?v=0.2.5','assets/v020_science.js?v=0.2.5','assets/v023_aggressiveness.js?v=0.2.5','assets/v025.js?v=0.2.5','assets/v025.css?v=0.2.5']:
        assert asset in index
    races=(static/'assets/v020.js').read_text()
    science=(static/'assets/v020_science.js').read_text()
    v023=(static/'assets/v023_aggressiveness.js').read_text()
    v025=(static/'assets/v025.js').read_text()
    css025=(static/'assets/v025.css').read_text()
    assert 'A-Rennen' in races and 'B-Rennen' in races and 'api/v2/races' in races
    assert 'Planungsaggressivität' in science
    assert all(label in science for label in ['Konservativ','Moderat','Aggressiv'])
    assert 'Sehr aggressiv' in v023 and 'very_progressive' in v023 and '2,5 %' in v023
    assert 'Deine Bestzeiten' in v025 and 'improvement_since_best_seconds' in v025
    assert '--nav-safe-compact' in css025 and 'v025-best-card' in css025
    subprocess.run(['node','--check',str(static/'app.js')],check=True)
    subprocess.run(['node','--check',str(static/'assets/v020.js')],check=True)
    subprocess.run(['node','--check',str(static/'assets/v020_science.js')],check=True)
    subprocess.run(['node','--check',str(static/'assets/v023_aggressiveness.js')],check=True)
    subprocess.run(['node','--check',str(static/'assets/v025.js')],check=True)

def test_ha_app_config_and_health_auto_export_gateway():
    cfg=yaml.safe_load((ROOT/'laufapp/config.yaml').read_text())
    assert cfg['arch']==['amd64'] and cfg['ingress'] is True and cfg['ingress_port']==8099
    assert cfg['schema']['openai_api_key']=='password'
    assert cfg['schema']['health_auto_export_token']=='password'
    assert cfg['ports']['8099/tcp'] is None and cfg['ports']['8100/tcp'] is None
    assert 'share:rw' in cfg.get('map',[])
    run=(ROOT/'laufapp/run.sh').read_text()
    assert 'health_auto_export_gateway:app' in run and '--port 8100' in run
    gateway=(ROOT/'laufapp/app/health_auto_export_gateway.py').read_text()
    assert '@app.post("/health-auto-export")' in gateway
    hae=(ROOT/'laufapp/app/health_auto_export_v026.py').read_text()
    assert 'hmac.compare_digest' in hae and 'MAX_BODY_BYTES' in hae
    assert not (ROOT/'laufapp/app/main_v030.py').exists()
    assert not (ROOT/'laufapp/app/ios_healthkit_sync.py').exists()


def test_large_uploads_use_home_assistant_ingress_streaming():
    cfg=yaml.safe_load((ROOT/'laufapp/config.yaml').read_text())
    assert cfg.get('ingress_stream') is True


def test_dockerfile_copy_sources_exist_in_build_context():
    import shlex
    context = ROOT / 'laufapp'
    dockerfile = (context / 'Dockerfile').read_text().splitlines()
    for raw in dockerfile:
        line = raw.strip()
        if not line or line.startswith('#') or not line.upper().startswith('COPY '):
            continue
        parts = shlex.split(line)
        args = [p for p in parts[1:] if not p.startswith('--')]
        assert len(args) >= 2, f'Invalid COPY instruction: {line}'
        for src in args[:-1]:
            assert not any(ch in src for ch in '*?['), f'Wildcard COPY not covered by test: {line}'
            assert (context / src.rstrip('/')).exists(), f'Missing Docker COPY source: {src}'
    text = (context / 'Dockerfile').read_text()
    assert 'COPY requirements.txt /tmp/requirements.txt' in text
    assert 'COPY app/requirements.txt /tmp/requirements.txt' not in text


def test_github_repository_layout():
    repo=yaml.safe_load((ROOT/'repository.yaml').read_text())
    assert repo['name']=='Laufapp Home Assistant Repository'
    assert repo['url']=='https://github.com/ansgarvh/laufapp-homeassistant'
    workflow=(ROOT/'.github/workflows/ci.yml').read_text()
    for required in ['pytest -q','python -m compileall','node --check','docker build','v023_aggressiveness.js','v025.js','health-auto-export','ci-secret']:
        assert required in workflow
    assert 'ios-build' not in workflow
    assert (ROOT/'requirements-dev.txt').is_file()
