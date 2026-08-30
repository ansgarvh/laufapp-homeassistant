import sqlite3

import health_auto_export_v026 as hae


class TrainingStub:
    def __init__(self):
        self.matched = []
    def auto_match_run(self, c, run_id):
        self.matched.append(run_id)


def conn():
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
    return c


def payload():
    return {
        "data": {
            "workouts": [{
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Running",
                "start": "2026-08-30 08:00:00 +0200",
                "end": "2026-08-30 09:00:00 +0200",
                "duration": 3600,
                "distance": {"qty": 12.0, "units": "km"},
                "activeEnergyBurned": {"qty": 850, "units": "kcal"},
                "elevationUp": {"qty": 120, "units": "m"},
                "avgHeartRate": {"qty": 145, "units": "bpm"},
                "stepCadence": {"qty": 172, "units": "spm"},
                "heartRateData": [
                    {"date": "2026-08-30 08:00:01 +0200", "Min": 130, "Avg": 134, "Max": 138, "units": "bpm", "source": "Apple Watch"}
                ],
                "runningPower": [
                    {"date": "2026-08-30 08:00:01 +0200", "qty": 310, "units": "W", "source": "Apple Watch"}
                ],
                "runningSpeed": [
                    {"date": "2026-08-30 08:00:01 +0200", "qty": 3.4, "units": "m/s", "source": "Apple Watch"}
                ],
                "runningStrideLength": [
                    {"date": "2026-08-30 08:00:01 +0200", "qty": 1.18, "units": "m", "source": "Apple Watch"}
                ],
                "runningVerticalOscillation": [
                    {"date": "2026-08-30 08:00:01 +0200", "qty": 8.3, "units": "cm", "source": "Apple Watch"}
                ],
                "runningGroundContactTime": [
                    {"date": "2026-08-30 08:00:01 +0200", "qty": 242, "units": "ms", "source": "Apple Watch"}
                ],
                "route": [
                    {"latitude": 50.775, "longitude": 6.083, "altitude": 180, "timestamp": "2026-08-30 08:00:00 +0200"},
                    {"latitude": 50.776, "longitude": 6.084, "altitude": 181, "timestamp": "2026-08-30 08:00:05 +0200"}
                ]
            }],
            "metrics": [
                {"name": "heart_rate_variability", "units": "ms", "data": [{"qty": 54, "date": "2026-08-30 06:00:00 +0200", "source": "Apple Watch"}]},
                {"name": "resting_heart_rate", "units": "bpm", "data": [{"qty": 48, "date": "2026-08-30 06:00:00 +0200"}]},
                {"name": "vo2_max", "units": "mL/kg/min", "data": [{"qty": 55.2, "date": "2026-08-30 09:00:00 +0200"}]},
                {"name": "sleep_analysis", "units": "hr", "data": [{"date": "2026-08-30", "totalSleep": 7.5, "sleepStart": "2026-08-29 22:30:00 +0200", "sleepEnd": "2026-08-30 06:00:00 +0200"}]}
            ]
        }
    }


def test_hae_v2_imports_detailed_run_and_is_idempotent():
    c = conn(); training = TrainingStub()
    first = hae.ingest(c, payload(), training, lambda *_: 0)
    assert first["runs_added"] == 1
    assert first["samples_added"] == 7
    assert first["gps_points_added"] == 2
    assert first["health_metrics_added"] == 4
    assert training.matched == [1]
    run = c.execute("SELECT * FROM runs").fetchone()
    assert run["external_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert abs(run["distance_km"] - 12.0) < 1e-9
    assert {r["metric_type"] for r in c.execute("SELECT * FROM run_samples")} == {
        "heart_rate", "running_speed", "running_power", "stride_length",
        "vertical_oscillation", "ground_contact_time", "cadence"
    }
    assert {r["metric_type"] for r in c.execute("SELECT * FROM health_metrics")} == {
        "hrv_sdnn", "resting_hr", "vo2max", "sleep_hours"
    }

    second = hae.ingest(c, payload(), training, lambda *_: 0)
    assert second["runs_existing"] == 1
    assert second["samples_added"] == 0
    assert second["gps_points_added"] == 0
    assert second["health_metrics_added"] == 0
    assert c.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1


def test_hae_units_and_validation():
    c = conn(); training = TrainingStub(); p = payload()
    p["data"]["workouts"][0]["distance"] = {"qty": 10, "units": "mi"}
    hae.ingest(c, p, training)
    assert abs(c.execute("SELECT distance_km FROM runs").fetchone()[0] - 16.09344) < 1e-5

    c = conn(); bad = payload(); bad["data"]["workouts"][0]["route"][0]["latitude"] = 120
    try:
        hae.ingest(c, bad, training)
        assert False, "invalid coordinate must be rejected"
    except ValueError:
        pass


def test_token_auth(monkeypatch):
    monkeypatch.setenv("LAUFAPP_HEALTH_AUTO_EXPORT_TOKEN", "secret-token")
    assert hae.authorized("Bearer secret-token", None)
    assert hae.authorized(None, "secret-token")
    assert not hae.authorized("Bearer wrong", None)
