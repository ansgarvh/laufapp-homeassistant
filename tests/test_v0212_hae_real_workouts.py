import math
import sqlite3

import health_auto_export_v0212 as hae


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


def long_real_shape():
    # Reduced fixture from the real 2026-08-30 HAE export. The original workout
    # has 10,094 GPS points, 2,050 HR samples and an activeEnergy time series but
    # no activeEnergyBurned summary.
    return {
        "data": {
            "workouts": [{
                "id": "DE382A1C-35E5-4F9F-8642-731906536CD9",
                "name": "Outdoor Ausführen",
                "start": "2026-08-30 07:19:04 +0200",
                "end": "2026-08-30 10:09:55 +0200",
                "duration": 10093.704308986664,
                "distance": {"qty": 34.02040232701416, "units": "km"},
                "avgHeartRate": {"qty": 142.23853658536586, "units": "count/min"},
                "stepCadence": {"qty": 164.8093418230725, "units": "count/min"},
                "totalEnergy": {"qty": 13084.452032564825, "units": "kJ"},
                "activeEnergy": [
                    {"date": "2026-08-30 07:19:06 +0200", "units": "kJ", "qty": 0.6859031325292064, "source": "Apple Watch"},
                    {"date": "2026-08-30 07:19:07 +0200", "units": "kJ", "qty": 0.8032913043353727, "source": "Apple Watch"},
                    {"date": "2026-08-30 07:19:08 +0200", "units": "kJ", "qty": 0.8032913043353727, "source": "Apple Watch"},
                ],
                "heartRateData": [
                    {"date": "2026-08-30 07:19:12 +0200", "Avg": 99, "Min": 99, "Max": 99, "units": "count/min"},
                    {"date": "2026-08-30 07:19:17 +0200", "Avg": 105, "Min": 104, "Max": 106, "units": "count/min"},
                ],
                "route": [
                    {"longitude": 6.092893926209142, "latitude": 50.78922626552115, "altitude": 163.94646463815553, "timestamp": "2026-08-30 07:19:05 +0200"},
                    {"longitude": 6.092929, "latitude": 50.789209, "altitude": 163.8, "timestamp": "2026-08-30 07:19:06 +0200"},
                ],
            }],
            "metrics": [],
        }
    }


def short_real_shape():
    # Reduced fixture from the real 2026-08-27 export with Route Data enabled.
    # Here HAE supplies both activeEnergyBurned and a time series; the explicit
    # workout summary must remain authoritative.
    return {
        "data": {
            "workouts": [{
                "id": "4518AF7C-C055-4FE9-80B4-7C94FB0F52EF",
                "name": "Outdoor Ausführen",
                "start": "2026-08-27 06:18:50 +0200",
                "end": "2026-08-27 06:23:39 +0200",
                "duration": 289.07137298583984,
                "distance": {"qty": 0.932501084243316, "units": "km"},
                "avgHeartRate": {"qty": 119.08620689655173, "units": "count/min"},
                "stepCadence": {"qty": 168.12456902254604, "units": "count/min"},
                "activeEnergyBurned": {"qty": 311.05315882908627, "units": "kJ"},
                "activeEnergy": [
                    {"date": "2026-08-27 06:18:53 +0200", "qty": 0.055339139484976034, "units": "kJ", "source": "Apple Watch"},
                    {"date": "2026-08-27 06:18:54 +0200", "qty": 0.7295233898659438, "units": "kJ", "source": "Apple Watch"},
                ],
                "heartRateData": [
                    {"date": "2026-08-27 06:18:54 +0200", "Avg": 103, "Min": 103, "Max": 103, "units": "count/min"},
                ],
                "route": [
                    {"longitude": 6.0903611648499565, "latitude": 50.79315240370018, "altitude": 163.09065474104136, "timestamp": "2026-08-27 06:18:55 +0200"},
                    {"longitude": 6.09039, "latitude": 50.793178, "altitude": 163.1, "timestamp": "2026-08-27 06:18:56 +0200"},
                ],
            }],
            "metrics": [],
        }
    }


def test_real_german_outdoor_name_is_imported_and_idempotent():
    c = conn()
    training = TrainingStub()
    payload = long_real_shape()

    first = hae.ingest(c, payload, training)
    assert first["runs_added"] == 1
    assert first["samples_added"] == 4  # 2 HR + cadence summary + separate total energy
    assert first["gps_points_added"] == 2
    assert training.matched == [1]

    run = c.execute("SELECT * FROM runs").fetchone()
    assert run["external_id"] == "DE382A1C-35E5-4F9F-8642-731906536CD9"
    assert math.isclose(run["distance_km"], 34.02040232701416, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(run["duration_s"], 10093.704308986664, rel_tol=0, abs_tol=1e-9)
    expected_kcal = (0.6859031325292064 + 0.8032913043353727 + 0.8032913043353727) / 4.184
    assert math.isclose(run["calories"], expected_kcal, rel_tol=0, abs_tol=1e-12)
    assert run["source"] == "apple_health_hae"

    total = c.execute(
        "SELECT metric_type,value,unit FROM run_samples WHERE metric_type='total_calories'"
    ).fetchone()
    assert total is not None
    assert total["unit"] == "kcal"
    assert math.isclose(total["value"], 13084.452032564825 / 4.184, rel_tol=0, abs_tol=1e-12)
    assert run["calories"] < total["value"]  # totalEnergy never replaces active calories

    second = hae.ingest(c, payload, training)
    assert second["runs_existing"] == 1
    assert second["samples_added"] == 0
    assert second["gps_points_added"] == 0
    assert c.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM run_samples WHERE metric_type='total_calories'").fetchone()[0] == 1


def test_explicit_active_energy_summary_beats_time_series():
    c = conn()
    training = TrainingStub()
    result = hae.ingest(c, short_real_shape(), training)
    assert result["runs_added"] == 1
    run = c.execute("SELECT * FROM runs").fetchone()
    assert math.isclose(run["distance_km"], 0.932501084243316, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(run["calories"], 311.05315882908627 / 4.184, rel_tol=0, abs_tol=1e-12)
    assert c.execute("SELECT COUNT(*) FROM gps_points").fetchone()[0] == 2
    assert c.execute("SELECT COUNT(*) FROM run_samples WHERE metric_type='total_calories'").fetchone()[0] == 0


def test_non_running_workout_is_still_not_imported():
    c = conn()
    training = TrainingStub()
    payload = short_real_shape()
    payload["data"]["workouts"][0]["id"] = "cycling-fixture"
    payload["data"]["workouts"][0]["name"] = "Outdoor Cycling"
    result = hae.ingest(c, payload, training)
    assert result["workouts_received"] == 1
    assert result["runs_added"] == 0
    assert c.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
