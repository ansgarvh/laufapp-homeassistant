import sys
from pathlib import Path

from fastapi.testclient import TestClient

APP = Path(__file__).resolve().parents[1] / "laufapp" / "app"
sys.path.insert(0, str(APP))
import main_v027 as main


def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("LAUFAPP_TRUSTED_INGRESS_ONLY", "1")
    monkeypatch.setenv("LAUFAPP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LAUFAPP_TRANSFER_DIR", str(tmp_path / "transfer"))
    monkeypatch.setenv("LAUFAPP_OPTIONS_FILE", str(tmp_path / "options.json"))


def test_production_guard_blocks_direct_remote_access(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    with TestClient(main.app, client=("198.51.100.23", 50000)) as c:
        assert c.get("/").status_code == 403


def test_production_guard_does_not_trust_forged_ingress_or_forwarding_headers(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    headers = {
        "X-Hass-Source": "core.ingress",
        "X-Ingress-Path": "/api/hassio_ingress/fake-token",
        "X-Forwarded-For": "127.0.0.1",
    }
    with TestClient(main.app, client=("198.51.100.23", 50000), headers=headers) as c:
        assert c.get("/").status_code == 403


def test_production_guard_allows_real_home_assistant_ingress_peer(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    with TestClient(main.app, client=("172.30.32.2", 50000)) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "Laufapp" in r.text


def test_production_guard_allows_only_local_healthcheck(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    with TestClient(main.app, client=("127.0.0.1", 50000)) as c:
        r = c.get("/api/health")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert c.get("/").status_code == 403
