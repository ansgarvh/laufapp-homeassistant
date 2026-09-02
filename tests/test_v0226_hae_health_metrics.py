from copy import deepcopy
from datetime import date, timedelta
import math
import sqlite3

import health_auto_export_v0226 as hae


class TrainingStub:
    def auto_match_run(self, c, run_id):
        raise AssertionError("metric-only payload must not match a run")


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


def current_hae_payload():
    return {
        "data": {
            "workouts": [],
            "metrics": [
                {
                    "name": "weight_body_mass",
                    "units": "kg",
                    "data": [
                        {
                            "qty": 88.4,
                            "date": "2026-09-01 07:00:00 +0200",
                            "source": "Withings",
                        }
                    ],
                },
                {
                    "name": "sleep_analysis",
                    "units": "hr",
                    "data": [
                        {
                            "date": "2026-09-01",
                            "sleepStart": "2026-08-31 22:45:00 +0200",
                            "sleepEnd": "2026-09-01 06:15:00 +0200",
                            "core": 4.2,
                            "rem": 1.5,
                            "deep": 1.1,
                            "awake": 0.7,
                            "inBed": 7.5,
                            "source": "Apple Watch",
                        }
                    ],
                },
                {
                    "name": "heart_rate_variability",
                    "units": "ms",
                    "data": [
                        {
                            "qty": 56,
                            "date": "2026-09-01 05:30:00 +0200",
                            "source": "Apple Watch",
                        }
                    ],
                },
                {
                    "name": "resting_heart_rate",
                    "units": "count/min",
                    "data": [
                        {
                            "qty": 49,
                            "date": "2026-09-01 05:30:00 +0200",
                            "source": "Apple Watch",
                        }
                    ],
                },
                {
                    "name": "vo2max",
                    "units": "mL/kg/min",
                    "data": [
                        {
                            "qty": 54.1,
                            "date": "2026-09-01 09:00:00 +0200",
                            "source": "Apple Watch",
                        }
                    ],
                },
            ],
        }
    }


def test_current_hae_metric_names_and_sleep_stages_are_imported_idempotently():
    c = conn()
    first = hae.ingest(c, current_hae_payload(), TrainingStub())
    assert first["health_metrics_added"] == 5
    assert first["health_metric_records_seen"] == {
        "body_mass": 1,
        "sleep_hours": 1,
        "hrv_sdnn": 1,
        "resting_hr": 1,
        "vo2max": 1,
    }
    rows = {
        row["metric_type"]: row
        for row in c.execute(
            "SELECT metric_type,value,unit,start_at,end_at FROM health_metrics"
        )
    }
    assert set(rows) == {"body_mass", "sleep_hours", "hrv_sdnn", "resting_hr", "vo2max"}
    assert rows["body_mass"]["value"] == 88.4
    assert rows["body_mass"]["unit"] == "kg"
    assert math.isclose(rows["sleep_hours"]["value"], 6.8)
    assert rows["sleep_hours"]["unit"] == "h"
    assert rows["sleep_hours"]["end_at"] == "2026-09-01T06:15:00+02:00"
    assert rows["hrv_sdnn"]["value"] == 56
    assert rows["hrv_sdnn"]["unit"] == "ms"
    assert rows["resting_hr"]["unit"] == "bpm"
    assert rows["vo2max"]["value"] == 54.1

    second = hae.ingest(c, current_hae_payload(), TrainingStub())
    assert second["health_metrics_added"] == 0
    assert second["health_metrics_updated"] == 0
    assert c.execute("SELECT COUNT(*) FROM health_metrics").fetchone()[0] == 5


def test_units_are_normalized_and_legacy_pound_rows_are_repaired():
    c = conn()
    c.execute(
        "INSERT INTO health_metrics(external_id,metric_type,start_at,value,unit,source) "
        "VALUES('legacy-lb','body_mass','2026-08-20T07:00:00+02:00',194,'lbs','health_auto_export')"
    )
    payload = {
        "data": {
            "workouts": [],
            "metrics": [
                {
                    "name": "Weight & Body Mass",
                    "units": "lb",
                    "data": [{"qty": 195, "date": "2026-09-02 07:00:00 +0200"}],
                },
                {
                    "name": "sleep_analysis",
                    "units": "min",
                    "data": [
                        {
                            "date": "2026-09-02",
                            "sleepStart": "2026-09-01 23:00:00 +0200",
                            "sleepEnd": "2026-09-02 06:30:00 +0200",
                            "core": 270,
                            "rem": 90,
                            "deep": 60,
                        }
                    ],
                },
                {
                    "name": "heart_rate_variability_sdnn",
                    "units": "s",
                    "data": [{"qty": 0.061, "date": "2026-09-02 05:00:00 +0200"}],
                },
            ],
        }
    }
    result = hae.ingest(c, deepcopy(payload), TrainingStub())
    assert result["health_metrics_added"] == 3
    assert result["legacy_weight_rows_repaired"] == 1

    legacy = c.execute(
        "SELECT value,unit FROM health_metrics WHERE external_id='legacy-lb'"
    ).fetchone()
    assert legacy["unit"] == "kg"
    assert math.isclose(legacy["value"], 194 * 0.45359237)

    latest = c.execute(
        "SELECT value,unit FROM health_metrics WHERE metric_type='body_mass' ORDER BY start_at DESC LIMIT 1"
    ).fetchone()
    assert latest["unit"] == "kg"
    assert math.isclose(latest["value"], 195 * 0.45359237)
    assert c.execute(
        "SELECT value FROM health_metrics WHERE metric_type='sleep_hours'"
    ).fetchone()[0] == 7.0
    assert c.execute(
        "SELECT value FROM health_metrics WHERE metric_type='hrv_sdnn'"
    ).fetchone()[0] == 61.0

    repeated = hae.ingest(c, deepcopy(payload), TrainingStub())
    assert repeated["health_metrics_added"] == 0
    assert repeated["health_metrics_updated"] == 0
    assert repeated["legacy_weight_rows_repaired"] == 0


def test_repeated_sleep_night_refreshes_partial_hae_value_without_duplicate():
    c = conn()
    partial = current_hae_payload()
    partial["data"]["metrics"] = [partial["data"]["metrics"][1]]
    partial_point = partial["data"]["metrics"][0]["data"][0]
    partial_point.update({"core": 2.0, "rem": 0.5, "deep": 0.5})

    first = hae.ingest(c, partial, TrainingStub())
    assert first["health_metrics_added"] == 1
    assert first["health_metrics_updated"] == 0
    assert c.execute("SELECT value FROM health_metrics").fetchone()[0] == 3.0

    complete = current_hae_payload()
    complete["data"]["metrics"] = [complete["data"]["metrics"][1]]
    second = hae.ingest(c, complete, TrainingStub())
    assert second["health_metrics_added"] == 0
    assert second["health_metrics_updated"] == 1
    row = c.execute("SELECT value,end_at FROM health_metrics").fetchone()
    assert math.isclose(row["value"], 6.8)
    assert row["end_at"] == "2026-09-01T06:15:00+02:00"
    assert c.execute("SELECT COUNT(*) FROM health_metrics").fetchone()[0] == 1


def test_invalid_health_units_and_values_fail_closed():
    c = conn()
    bad_weight = current_hae_payload()
    bad_weight["data"]["metrics"] = [
        {
            "name": "weight_body_mass",
            "units": "unknown",
            "data": [{"qty": 88, "date": "2026-09-01"}],
        }
    ]
    try:
        hae.ingest(c, bad_weight, TrainingStub())
        assert False, "unknown weight units must not be stored as kilograms"
    except ValueError as exc:
        assert "Gewichtseinheit" in str(exc)

    bad_hrv = current_hae_payload()
    bad_hrv["data"]["metrics"] = [
        {
            "name": "heart_rate_variability",
            "units": "ms",
            "data": [{"qty": 5000, "date": "2026-09-01"}],
        }
    ]
    try:
        hae.ingest(c, bad_hrv, TrainingStub())
        assert False, "implausible HRV must be rejected"
    except ValueError as exc:
        assert "HRV" in str(exc)


def test_current_health_metrics_end_to_end_through_hardened_http(monkeypatch, setup_client):
    token = "9f4a6c2d8e1b7a305c9d4e6f1a2b8c70d5e3f9a1c6b4d8e2f7a0c3b5d9e1f6a4"
    monkeypatch.setenv("LAUFAPP_HEALTH_AUTO_EXPORT_TOKEN", token)
    payload = current_hae_payload()
    today = date.today()
    yesterday = today - timedelta(days=1)
    for metric in payload["data"]["metrics"]:
        point = metric["data"][0]
        if metric["name"] == "sleep_analysis":
            point["date"] = today.isoformat()
            point["sleepStart"] = f"{yesterday.isoformat()} 22:45:00 +0200"
            point["sleepEnd"] = f"{today.isoformat()} 06:15:00 +0200"
        else:
            point["date"] = f"{today.isoformat()} 07:00:00 +0200"

    response = setup_client.post(
        "/api/v2/health-auto-export",
        headers={"X-Laufapp-Token": token},
        json=payload,
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["ok"] is True
    assert result["health_metrics_added"] == 5
    assert result["health_metrics_updated"] == 0
    assert result["legacy_weight_rows_repaired"] == 0
    assert "predictions" not in result

    health = setup_client.get("/api/dashboard").json()["health"]
    assert health["body_mass"]["latest"] == 88.4
    assert health["body_mass"]["unit"] == "kg"
    assert health["sleep_hours"]["latest"] == 6.8
    assert health["hrv_sdnn"]["latest"] == 56
    assert health["resting_hr"]["latest"] == 49
    assert health["vo2max"]["latest"] == 54.1

    trends = setup_client.get("/api/progress/trends?period=3m")
    assert trends.status_code == 200, trends.text
    week = next(
        item for item in trends.json()["weeks"] if item["body_mass"] is not None
    )
    assert week["body_mass"] == 88.4
    assert week["sleep_hours"] == 6.8
    assert week["hrv_sdnn"] == 56
