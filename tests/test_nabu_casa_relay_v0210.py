from pathlib import Path

from fastapi.testclient import TestClient

import health_auto_export_gateway as gateway
from db import init_db


STRONG_TOKEN = "9f4a6c2d8e1b7a305c9d4e6f1a2b8c70d5e3f9a1c6b4d8e2f7a0c3b5d9e1f6a4"
ROOT = Path(__file__).resolve().parents[1]


def _payload():
    return {
        "data": {
            "workouts": [
                {
                    "id": "nabu-relay-run-1",
                    "name": "Running",
                    "start": "2026-08-30 12:00:00 +0200",
                    "end": "2026-08-30 12:30:00 +0200",
                    "duration": 1800,
                    "distance": {"qty": 5.0, "units": "km"},
                    "heartRateData": [
                        {
                            "date": "2026-08-30 12:00:01 +0200",
                            "Avg": 145,
                            "units": "bpm",
                        }
                    ],
                    "runningPower": [
                        {
                            "date": "2026-08-30 12:00:01 +0200",
                            "qty": 300,
                            "units": "W",
                        }
                    ],
                    "route": [
                        {
                            "latitude": 50.775,
                            "longitude": 6.083,
                            "altitude": 180,
                            "timestamp": "2026-08-30 12:00:00 +0200",
                        }
                    ],
                }
            ],
            "metrics": [
                {
                    "name": "Resting Heart Rate",
                    "units": "bpm",
                    "data": [{"qty": 49, "date": "2026-08-30 06:00:00 +0200"}],
                }
            ],
        }
    }


def _configure(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("LAUFAPP_TRUSTED_INGRESS_ONLY", "0")
    monkeypatch.setenv("LAUFAPP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("LAUFAPP_TRANSFER_DIR", str(tmp_path / "transfer"))
    monkeypatch.setenv("LAUFAPP_OPTIONS_FILE", str(tmp_path / "options.json"))
    monkeypatch.setenv("LAUFAPP_HEALTH_AUTO_EXPORT_TOKEN", STRONG_TOKEN)
    # Production run.sh starts the main process and waits for its health check
    # before starting the gateway. That main startup initializes/migrates the DB.
    # The isolated gateway unit test must explicitly model the same precondition.
    init_db(data_dir / "laufapp.sqlite3")


def test_home_assistant_relay_requires_dedicated_x_token(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    with TestClient(gateway.app) as client:
        missing = client.post("/home-assistant-relay", json=_payload())
        bearer_only = client.post(
            "/home-assistant-relay",
            headers={"Authorization": f"Bearer {STRONG_TOKEN}"},
            json=_payload(),
        )
    assert missing.status_code == 401
    assert bearer_only.status_code == 401


def test_home_assistant_relay_imports_and_retries_idempotently(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    headers = {"X-Laufapp-Token": STRONG_TOKEN}
    with TestClient(gateway.app) as client:
        first = client.post("/home-assistant-relay", headers=headers, json=_payload())
        second = client.post("/home-assistant-relay", headers=headers, json=_payload())
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    first_body = first.json()
    second_body = second.json()
    assert first_body["ok"] is True
    assert first_body["runs_added"] == 1
    assert first_body["samples_added"] == 2
    assert first_body["gps_points_added"] == 1
    assert first_body["health_metrics_added"] == 1
    assert second_body["ok"] is True
    assert second_body["runs_existing"] == 1
    assert second_body["samples_added"] == 0
    assert second_body["gps_points_added"] == 0
    assert second_body["health_metrics_added"] == 0
    assert "predictions" not in first_body
    assert "version" not in first_body


def test_home_assistant_relay_examples_do_not_embed_secrets_and_mark_template_path_legacy():
    rest = (ROOT / "home_assistant/rest_command_laufapp_nabu_casa.yaml.example").read_text()
    automation = (ROOT / "home_assistant/automation_laufapp_nabu_casa.yaml.example").read_text()
    direct = (ROOT / "home_assistant/laufapp_hae_relay_configuration.yaml.example").read_text()
    docs = (ROOT / "NABU_CASA_HEALTH_SYNC.md").read_text()

    assert "http://c87ed7df-laufapp:8100/home-assistant-relay" in rest
    assert "X-Laufapp-Token: !secret laufapp_health_auto_export_token" in rest
    assert STRONG_TOKEN not in rest
    assert "LEGACY / SMALL-PAYLOAD EXAMPLE ONLY" in rest
    assert "REPLACE_WITH_A_NEW_RANDOM_WEBHOOK_ID" in automation
    assert "local_only: false" in automation
    assert "262144" in automation
    assert "trigger.json | to_json" in automation
    assert "laufapp_hae_relay:" in direct
    assert "!secret laufapp_hae_webhook_id" in direct
    assert "!secret laufapp_health_auto_export_token" in direct
    assert "Previous 7 Days" in docs
    assert ".ui.nabu.casa/api/webhook/" in docs
    assert "Do not forward ports 8099 or 8100" in docs
