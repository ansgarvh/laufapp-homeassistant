import sqlite3

import ios_healthkit_sync as sync


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
        CREATE TABLE runs(id INTEGER PRIMARY KEY AUTOINCREMENT,external_id TEXT UNIQUE,started_at TEXT NOT NULL,ended_at TEXT,distance_km REAL NOT NULL,duration_s REAL NOT NULL,avg_hr REAL,elevation_m REAL,calories REAL,source TEXT NOT NULL DEFAULT 'manual');
        CREATE TABLE run_samples(id INTEGER PRIMARY KEY AUTOINCREMENT,external_id TEXT UNIQUE,run_id INTEGER NOT NULL,metric_type TEXT NOT NULL,sampled_at TEXT NOT NULL,value REAL NOT NULL,unit TEXT NOT NULL DEFAULT '',source TEXT NOT NULL DEFAULT 'apple_health');
        CREATE TABLE gps_points(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id INTEGER NOT NULL,sampled_at TEXT NOT NULL,latitude REAL NOT NULL,longitude REAL NOT NULL,elevation_m REAL,sequence INTEGER NOT NULL,source TEXT NOT NULL DEFAULT 'apple_health',UNIQUE(run_id,source,sequence));
        CREATE TABLE health_metrics(id INTEGER PRIMARY KEY AUTOINCREMENT,external_id TEXT UNIQUE,metric_type TEXT NOT NULL,start_at TEXT NOT NULL,end_at TEXT,value REAL NOT NULL,unit TEXT NOT NULL DEFAULT '',source TEXT NOT NULL DEFAULT 'apple_health');
        """
    )
    return c


def payload():
    return {
        "schema_version": 1,
        "source": "laufapp_ios",
        "device_id": "iphone-test",
        "workouts": [{
            "id": "workout-uuid-1",
            "activity_type": "running",
            "start_at": "2026-08-30T08:00:00+02:00",
            "end_at": "2026-08-30T09:00:00+02:00",
            "distance_km": 12.0,
            "duration_s": 3600,
            "avg_hr": 145,
            "elevation_m": 120,
            "calories": 900,
            "samples": [
                {"id": "s-distance", "type": "distance", "at": "2026-08-30T08:01:00+02:00", "value": 0.2, "unit": "km"},
                {"id": "s-hr", "type": "heart_rate", "at": "2026-08-30T08:01:00+02:00", "value": 140, "unit": "count/min"},
                {"id": "s-power", "type": "running_power", "at": "2026-08-30T08:01:00+02:00", "value": 310, "unit": "W"},
            ],
            "route": [
                {"at": "2026-08-30T08:00:00+02:00", "lat": 50.775, "lon": 6.083, "elevation_m": 180},
                {"at": "2026-08-30T08:00:05+02:00", "lat": 50.776, "lon": 6.084, "elevation_m": 181},
            ],
        }],
        "metrics": [
            {"id": "metric-hrv", "type": "hrv_sdnn", "start_at": "2026-08-30T06:00:00+02:00", "end_at": "2026-08-30T06:01:00+02:00", "value": 54.0, "unit": "ms"}
        ],
    }


def test_healthkit_payload_imports_detailed_run_and_is_idempotent():
    c = conn(); training = TrainingStub()
    first = sync.ingest_healthkit_payload(c, payload(), training, lambda *_: 0)
    assert first["workouts_added"] == 1
    assert first["samples_added"] == 3
    assert first["gps_points_added"] == 2
    assert first["health_metrics_added"] == 1
    assert training.matched == [1]
    run = c.execute("SELECT * FROM runs").fetchone()
    assert run["external_id"] == "workout-uuid-1"
    assert run["source"] == "apple_health_live"
    assert {r["metric_type"] for r in c.execute("SELECT * FROM run_samples")} == {"distance", "heart_rate", "running_power"}

    second = sync.ingest_healthkit_payload(c, payload(), training, lambda *_: 0)
    assert second["workouts_existing"] == 1
    assert second["samples_added"] == 0
    assert second["gps_points_added"] == 0
    assert second["health_metrics_added"] == 0
    assert c.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1


def test_healthkit_rejects_invalid_schema_and_coordinates():
    c = conn(); training = TrainingStub()
    bad = payload(); bad["schema_version"] = 99
    try:
        sync.ingest_healthkit_payload(c, bad, training)
        assert False, "expected invalid schema"
    except ValueError:
        pass
    bad = payload(); bad["workouts"][0]["route"][0]["lat"] = 120
    try:
        sync.ingest_healthkit_payload(c, bad, training)
        assert False, "expected invalid coordinate"
    except ValueError:
        pass
