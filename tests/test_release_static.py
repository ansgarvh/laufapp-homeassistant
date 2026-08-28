from pathlib import Path
import json, subprocess, yaml
ROOT=Path(__file__).resolve().parents[1]

def test_versions_and_assets():
    cfg=yaml.safe_load((ROOT/'laufapp/config.yaml').read_text())
    assert cfg['version']=='0.1.3'
    assert 'APP_VERSION = "0.1.3"' in (ROOT/'laufapp/app/db.py').read_text()
    static=ROOT/'laufapp/app/static'
    for name in ['index.html','styles.css','app.js','manifest.webmanifest','sw.js','icon-192.png','icon-512.png']:assert (static/name).exists()
    m=json.loads((static/'manifest.webmanifest').read_text());assert m['display']=='standalone'
    subprocess.run(['node','--check',str(static/'app.js')],check=True)

def test_ha_app_config():
    cfg=yaml.safe_load((ROOT/'laufapp/config.yaml').read_text())
    assert cfg['arch']==['amd64'] and cfg['ingress'] is True and cfg['ingress_port']==8099
    assert cfg['schema']['openai_api_key']=='password'
    assert 'share:rw' in cfg.get('map',[])


def test_dockerfile_copy_sources_exist_in_build_context():
    """Regression: every local Docker COPY source must exist under laufapp build context."""
    import shlex
    context = ROOT / 'laufapp'
    dockerfile = (context / 'Dockerfile').read_text().splitlines()
    for raw in dockerfile:
        line = raw.strip()
        if not line or line.startswith('#') or not line.upper().startswith('COPY '):
            continue
        parts = shlex.split(line)
        # Current Dockerfile uses simple COPY syntax; ignore flags defensively.
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
    for required in ['pytest -q','python -m compileall','node --check','docker build']:
        assert required in workflow
    assert (ROOT/'requirements-dev.txt').is_file()
