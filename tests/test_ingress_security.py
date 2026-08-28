import os, sys
from pathlib import Path
from fastapi.testclient import TestClient

APP=Path(__file__).resolve().parents[1]/"laufapp"/"app"
sys.path.insert(0,str(APP))
import main

def test_production_guard_blocks_direct_remote_access(monkeypatch,tmp_path):
    monkeypatch.setenv("LAUFAPP_TRUSTED_INGRESS_ONLY","1")
    monkeypatch.setenv("LAUFAPP_DATA_DIR",str(tmp_path/"data"))
    with TestClient(main.app,client=("198.51.100.23",50000)) as c:
        r=c.get("/")
        assert r.status_code==403

def test_production_guard_allows_home_assistant_ingress_even_with_remote_client_ip(monkeypatch,tmp_path):
    monkeypatch.setenv("LAUFAPP_TRUSTED_INGRESS_ONLY","1")
    monkeypatch.setenv("LAUFAPP_DATA_DIR",str(tmp_path/"data"))
    headers={"X-Hass-Source":"core.ingress","X-Ingress-Path":"/api/hassio_ingress/test-token"}
    with TestClient(main.app,client=("144.178.81.189",50000),headers=headers) as c:
        r=c.get("/")
        assert r.status_code==200
        assert "Laufapp" in r.text

def test_production_guard_allows_local_healthcheck(monkeypatch,tmp_path):
    monkeypatch.setenv("LAUFAPP_TRUSTED_INGRESS_ONLY","1")
    monkeypatch.setenv("LAUFAPP_DATA_DIR",str(tmp_path/"data"))
    with TestClient(main.app,client=("127.0.0.1",50000)) as c:
        r=c.get("/api/health")
        assert r.status_code==200
        assert r.json()["ok"] is True
