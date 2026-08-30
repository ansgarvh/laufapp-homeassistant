import asyncio
import sqlite3

from fastapi.testclient import TestClient

import health_auto_export_v027 as hae
import main_v027


STRONG_TOKEN = "9f4a6c2d8e1b7a305c9d4e6f1a2b8c70d5e3f9a1c6b4d8e2f7a0c3b5d9e1f6a4"


def minimal_payload(distance=5.0):
    return {
        "data": {
            "workouts": [
                {
                    "id": "security-run-1",
                    "name": "Running",
                    "start": "2026-08-30 08:00:00 +0200",
                    "end": "2026-08-30 08:30:00 +0200",
                    "duration": 1800,
                    "distance": {"qty": distance, "units": "km"},
                    "heartRateData": [
                        {
                            "date": "2026-08-30 08:00:01 +0200",
                            "Avg": 145,
                            "units": "bpm",
                        }
                    ],
                    "route": [],
                }
            ],
            "metrics": [],
        }
    }


def _configure_test_app(monkeypatch, tmp_path, *, ingress="0", token=STRONG_TOKEN):
    monkeypatch.setenv("LAUFAPP_TRUSTED_INGRESS_ONLY", ingress)
    monkeypatch.setenv("LAUFAPP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LAUFAPP_TRANSFER_DIR", str(tmp_path / "transfer"))
    monkeypatch.setenv("LAUFAPP_OPTIONS_FILE", str(tmp_path / "options.json"))
    monkeypatch.setenv("LAUFAPP_HEALTH_AUTO_EXPORT_TOKEN", token)


def test_runtime_ingress_rejects_forged_proxy_and_ingress_headers(monkeypatch, tmp_path):
    _configure_test_app(monkeypatch, tmp_path, ingress="1")
    forged = {
        "X-Forwarded-For": "127.0.0.1",
        "X-Hass-Source": "core.ingress",
        "X-Ingress-Path": "/api/hassio_ingress/forged",
    }
    with TestClient(main_v027.app, client=("198.51.100.23", 50000), headers=forged) as c:
        assert c.get("/").status_code == 403


def test_runtime_ingress_accepts_real_ha_peer_and_loopback_only_for_health(monkeypatch, tmp_path):
    _configure_test_app(monkeypatch, tmp_path, ingress="1")
    with TestClient(main_v027.app, client=("172.30.32.2", 50000)) as c:
        assert c.get("/").status_code == 200
    with TestClient(main_v027.app, client=("127.0.0.1", 50000)) as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/").status_code == 403


def test_weak_sync_token_is_refused(monkeypatch, tmp_path):
    _configure_test_app(monkeypatch, tmp_path, token="secret-token")
    with TestClient(main_v027.app) as c:
        r = c.post(
            "/api/v2/health-auto-export",
            headers={"Authorization": "Bearer secret-token"},
            json=minimal_payload(),
        )
    assert r.status_code == 503
    assert "mindestens" in r.json()["detail"]


def test_sync_requires_json_and_enforces_streaming_size_limit(monkeypatch, tmp_path):
    _configure_test_app(monkeypatch, tmp_path)
    with TestClient(main_v027.app) as c:
        r = c.post(
            "/api/v2/health-auto-export",
            headers={"Authorization": f"Bearer {STRONG_TOKEN}", "Content-Type": "text/plain"},
            content=b"{}",
        )
        assert r.status_code == 415
        # Patch the parser module actually resolved by the request handler.
        # Newer release wrappers may replace main_v027.hae while preserving the
        # same security contract.
        monkeypatch.setattr(main_v027.hae, "MAX_BODY_BYTES", 64)
        r = c.post(
            "/api/v2/health-auto-export",
            headers={"Authorization": f"Bearer {STRONG_TOKEN}", "Content-Type": "application/json"},
            content=b"{" + b" " * 64 + b"}",
        )
        assert r.status_code == 413


def test_sync_stream_timeout(monkeypatch):
    class SlowRequest:
        headers = {"content-type": "application/json"}

        async def stream(self):
            yield b"{"
            await asyncio.sleep(0.05)
            yield b"}"

    monkeypatch.setattr(main_v027, "REQUEST_BODY_TIMEOUT_SECONDS", 0.01)

    async def run():
        try:
            await main_v027._read_limited_json(SlowRequest())
            assert False, "slow upload must time out"
        except main_v027.HTTPException as exc:
            assert exc.status_code == 408

    asyncio.run(run())


def test_sync_response_is_write_only_and_uuid_collision_is_rejected(monkeypatch, tmp_path):
    _configure_test_app(monkeypatch, tmp_path)
    headers = {"Authorization": f"Bearer {STRONG_TOKEN}"}
    with TestClient(main_v027.app) as c:
        first = c.post("/api/v2/health-auto-export", headers=headers, json=minimal_payload())
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["ok"] is True and body["runs_added"] == 1
        assert "predictions" not in body
        assert "version" not in body
        collision = c.post(
            "/api/v2/health-auto-export",
            headers=headers,
            json=minimal_payload(distance=8.0),
        )
        assert collision.status_code == 422
        assert "kollidiert" in collision.json()["detail"]


def test_cross_source_samples_are_not_duplicated():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE runs(id INTEGER PRIMARY KEY AUTOINCREMENT,external_id TEXT UNIQUE,started_at TEXT NOT NULL,ended_at TEXT,distance_km REAL NOT NULL,duration_s REAL NOT NULL,avg_hr REAL,elevation_m REAL,calories REAL,source TEXT NOT NULL DEFAULT 'manual');
        CREATE TABLE run_samples(id INTEGER PRIMARY KEY AUTOINCREMENT,external_id TEXT UNIQUE,run_id INTEGER NOT NULL,metric_type TEXT NOT NULL,sampled_at TEXT NOT NULL,value REAL NOT NULL,unit TEXT NOT NULL DEFAULT '',source TEXT NOT NULL DEFAULT 'apple_health');
        CREATE TABLE gps_points(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id INTEGER NOT NULL,sampled_at TEXT NOT NULL,latitude REAL NOT NULL,longitude REAL NOT NULL,elevation_m REAL,sequence INTEGER NOT NULL,source TEXT NOT NULL DEFAULT 'apple_health',UNIQUE(run_id,source,sequence));
        CREATE TABLE health_metrics(id INTEGER PRIMARY KEY AUTOINCREMENT,external_id TEXT UNIQUE,metric_type TEXT NOT NULL,start_at TEXT NOT NULL,end_at TEXT,value REAL NOT NULL,unit TEXT NOT NULL DEFAULT '',source TEXT NOT NULL DEFAULT 'apple_health');
        """
    )
    c.execute(
        "INSERT INTO runs(external_id,started_at,ended_at,distance_km,duration_s,source) VALUES(?,?,?,?,?,?)",
        ("security-run-1", "2026-08-30T08:00:00+02:00", "2026-08-30T08:30:00+02:00", 5.0, 1800, "apple_health"),
    )
    c.execute(
        "INSERT INTO run_samples(external_id,run_id,metric_type,sampled_at,value,unit,source) VALUES(?,?,?,?,?,?,?)",
        ("xml-hr", 1, "heart_rate", "2026-08-30T08:00:01+02:00", 145, "bpm", "apple_health"),
    )

    class Training:
        def auto_match_run(self, *_):
            raise AssertionError("existing run must not be matched again")

    result = hae.ingest(c, minimal_payload(), Training())
    assert result["runs_existing"] == 1
    assert result["samples_added"] == 0
    assert c.execute("SELECT COUNT(*) FROM run_samples").fetchone()[0] == 1
