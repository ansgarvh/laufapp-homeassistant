from pathlib import Path
import json, subprocess, yaml
ROOT=Path(__file__).resolve().parents[1]

def test_versions_and_assets():
    cfg=yaml.safe_load((ROOT/'laufapp/config.yaml').read_text())
    assert cfg['version']=='0.2.16'
    assert 'APP_VERSION = "0.2.16"' in (ROOT/'laufapp/app/main_v0216.py').read_text()
    assert 'ARG BUILD_VERSION=0.2.16' in (ROOT/'laufapp/Dockerfile').read_text()
    assert 'main_v0216:app' in (ROOT/'laufapp/run.sh').read_text()
    assert '# Laufapp v0.2.16' in (ROOT/'README.md').read_text()
    assert '## v0.2.16 – 2026-08-31' in (ROOT/'CHANGELOG.md').read_text()
    assert (ROOT/'RELEASE_NOTES_v0.2.16.md').exists()
    assert 'Laufapp v0.2.16' in (ROOT/'RELEASE_NOTES_v0.2.16.md').read_text()
    static=ROOT/'laufapp/app/static'
    for name in ['index.html','styles.css','bugfix.css','app.js','manifest.webmanifest','sw.js','icon-192.png','icon-512.png','assets/bugfix.css','assets/v020.js','assets/v020.css','assets/v020_science.js','assets/v020_science.css','assets/v023_aggressiveness.js','assets/v025.js','assets/v025.css','assets/v0213.js','assets/v0213.css','assets/v0214.js','assets/v0214.css','assets/v0215.css']:assert (static/name).exists()
    m=json.loads((static/'manifest.webmanifest').read_text());assert m['display']=='standalone'
    sw=(static/'sw.js').read_text()
    assert "const CACHE='laufapp-v0.2.16'" in sw
    assert 'assets/v0213.js?v=0.2.13' in sw and 'assets/v0213.css?v=0.2.13' in sw and 'assets/v0215.css?v=0.2.15' in sw
    assert 'assets/v0214.js?v=0.2.14' not in sw and 'assets/v0214.css?v=0.2.14' not in sw
    index=(static/'index.html').read_text()
    for asset in ['app.js?v=0.2.16','assets/bugfix.css?v=0.2.5','assets/v020.js?v=0.2.5','assets/v020_science.js?v=0.2.5','assets/v023_aggressiveness.js?v=0.2.5','assets/v025.js?v=0.2.5','assets/v025.css?v=0.2.5','assets/v0213.js?v=0.2.13','assets/v0213.css?v=0.2.13','assets/v0215.css?v=0.2.15']:
        assert asset in index
    races=(static/'assets/v020.js').read_text()
    science=(static/'assets/v020_science.js').read_text()
    v023=(static/'assets/v023_aggressiveness.js').read_text()
    v025=(static/'assets/v025.js').read_text()
    css025=(static/'assets/v025.css').read_text()
    v0213=(static/'assets/v0213.js').read_text()
    assert 'A-Rennen' in races and 'B-Rennen' in races and 'api/v2/races' in races
    assert 'Planungsaggressivität' in science
    assert all(label in science for label in ['Konservativ','Moderat','Aggressiv'])
    assert 'Sehr aggressiv' in v023 and 'very_progressive' in v023 and '2,5 %' in v023
    assert 'Deine Bestzeiten' in v025 and 'improvement_since_best_seconds' in v025
    assert '--nav-safe-compact' in css025 and 'v025-best-card' in css025
    assert 'Trainingsentwicklung' in v0213 and 'api/progress/trends' in v0213
    subprocess.run(['node','--check',str(static/'app.js')],check=True)
    subprocess.run(['node','--check',str(static/'assets/v020.js')],check=True)
    subprocess.run(['node','--check',str(static/'assets/v020_science.js')],check=True)
    subprocess.run(['node','--check',str(static/'assets/v023_aggressiveness.js')],check=True)
    subprocess.run(['node','--check',str(static/'assets/v025.js')],check=True)
    subprocess.run(['node','--check',str(static/'assets/v0213.js')],check=True)

def test_ha_app_config_and_health_auto_export_gateway():
    cfg=yaml.safe_load((ROOT/'laufapp/config.yaml').read_text())
    assert cfg['arch']==['amd64'] and cfg['ingress'] is True and cfg['ingress_port']==8099
    assert cfg['schema']['openai_api_key']=='password'
    assert cfg['schema']['health_auto_export_token']=='password'
    assert cfg['ports']['8099/tcp'] is None and cfg['ports']['8100/tcp'] is None
    assert not cfg.get('map')
    assert 'Home-Assistant-Relay' in cfg['ports_description']['8100/tcp']
    run=(ROOT/'laufapp/run.sh').read_text()
    assert 'health_auto_export_gateway:app' in run and '--port 8100' in run
    assert '--no-proxy-headers' in run and '--no-server-header' in run
    assert '--forwarded-allow-ips' not in run
    assert 'LAUFAPP_SHUTDOWN signal=' in run
    assert 'LAUFAPP_CHILD_EXIT child=' in run
    assert 'wait -n -p EXITED_PID' in run
    subprocess.run(['bash','-n',str(ROOT/'laufapp/run.sh')],check=True)
    gateway=(ROOT/'laufapp/app/health_auto_export_gateway.py').read_text()
    assert '@app.post("/health-auto-export")' in gateway
    assert '@app.post("/home-assistant-relay")' in gateway
    assert 'from main_v0216 import APP_VERSION' in gateway
    assert 'LAUFAPP_HAE_RELAY_OK transport=nabu_casa' in gateway
    assert 'openapi_url=None' in gateway and 'Cache-Control' in gateway
    hae=(ROOT/'laufapp/app/health_auto_export_v027.py').read_text()
    assert 'MIN_TOKEN_LENGTH = 48' in hae and 'previous.authorized' in hae
    assert 'Workout-ID kollidiert' in hae
    compat=(ROOT/'laufapp/app/health_auto_export_v0212.py').read_text()
    assert 'outdoor ausführen' in compat.casefold()
    assert '_active_energy_series_kcal' in compat
    assert 'totalEnergy' in compat and 'must not be substituted' in compat
    runtime=(ROOT/'laufapp/app/main_v027.py').read_text()
    assert 'HOME_ASSISTANT_INTERNAL_NETWORK = ipaddress.ip_network("172.30.32.0/23")' in runtime
    assert 'HOME_ASSISTANT_INGRESS_PROXY = ipaddress.ip_address("172.30.32.2")' in runtime
    assert 'x-remote-user-id' in runtime and 'x-ingress-path' in runtime
    assert 'LAUFAPP_INGRESS_BLOCKED' in runtime
    assert 'request.stream()' in runtime
    assert 'Content-Type application/json erforderlich' in runtime
    assert '"predictions"' not in runtime.split('return {"ok": True, **result}',1)[0][-500:]
    hardened=(ROOT/'laufapp/app/main_v0213.py').read_text()
    assert 'Cross-Site-Schreibzugriff abgelehnt' in hardened
    assert 'Content-Security-Policy' in hardened
    assert '/api/progress/trends' in hardened
    assert '/api/system/prepare-repository-transfer' in hardened
    diag=(ROOT/'laufapp/app/main_v028.py').read_text()
    assert '_HealthcheckAccessFilter' in diag
    assert '{"/api/health", "/health"}' in diag
    assert '/api/apple-health/import-jobs/{job_id}/diagnostics' in diag
    imports=(ROOT/'laufapp/app/import_jobs.py').read_text()
    assert '.diagnostics.jsonl' in imports
    assert 'traceback.format_exc()' in imports
    assert 'resumed_after_restart' in imports
    assert (ROOT/'laufapp/app/main_v0214.py').exists() and (ROOT/'laufapp/app/main_v0215.py').exists()
    assert not (ROOT/'laufapp/app/main_v030.py').exists()
    assert not (ROOT/'laufapp/app/ios_healthkit_sync.py').exists()


def test_direct_home_assistant_webhook_relay_is_pinned_and_bounded():
    component=ROOT/'custom_components/laufapp_hae_relay'
    assert (component/'__init__.py').exists() and (component/'manifest.json').exists()
    manifest=json.loads((component/'manifest.json').read_text())
    assert manifest['domain']=='laufapp_hae_relay'
    assert manifest['version']=='0.2.16'
    assert manifest['requirements']==[]
    assert 'webhook' in manifest['dependencies']
    source=(component/'__init__.py').read_text()
    assert 'TARGET_URL = "http://c87ed7df-laufapp:8100/home-assistant-relay"' in source
    assert 'MAX_BODY_BYTES = 16 * 1024 * 1024' in source
    assert 'MAX_REQUESTS_PER_MINUTE = 12' in source
    assert 'MAX_CONCURRENT_FORWARDS = 3' in source
    assert 'READ_TIMEOUT_SECONDS = 120' in source
    assert 'allowed_methods=("POST",)' in source
    assert 'local_only=False' in source
    assert 'X-Laufapp-Token' in source
    assert 'async_get_clientsession' in source
    assert 'trigger.json' not in source
    cfg=(ROOT/'home_assistant/laufapp_hae_relay_configuration.yaml.example').read_text()
    assert 'laufapp_hae_relay:' in cfg
    assert '!secret laufapp_hae_webhook_id' in cfg
    assert '!secret laufapp_health_auto_export_token' in cfg
    assert not (ROOT/'home_assistant/automation_laufapp_nabu_casa.yaml.example').exists()
    assert not (ROOT/'home_assistant/rest_command_laufapp_nabu_casa.yaml.example').exists()
    docs=(ROOT/'NABU_CASA_HEALTH_SYNC.md').read_text()
    assert '.ui.nabu.casa/api/webhook/' in docs
    assert 'Template output exceeded maximum size of 262144 characters' in docs


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


def test_github_repository_layout_and_security_audit():
    repo=yaml.safe_load((ROOT/'repository.yaml').read_text())
    assert repo['name']=='Laufapp Home Assistant Repository'
    assert repo['url']=='https://github.com/ansgarvh/laufapp-homeassistant'
    workflow=(ROOT/'.github/workflows/ci.yml').read_text()
    for required in ['pytest -q','python -m compileall','custom_components/laufapp_hae_relay','node --check','docker build','v023_aggressiveness.js','v025.js','health-auto-export','home-assistant-relay','pip-audit','X-Forwarded-For','172.30.32.0/23','X-Remote-User-Id']:
        assert required in workflow
    security=(ROOT/'.github/workflows/security.yml').read_text()
    assert 'custom_components/laufapp_hae_relay' in security
    assert 'secret_history_scan.py' in security
    assert 'fetch-depth: 0' in security
    assert 'python -m pip check' in security
    assert 'ios-build' not in workflow
    assert 'pip-audit==2.10.1' in (ROOT/'requirements-dev.txt').read_text()
