from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from progress_trends_v0213 import build_training_trends


ROOT = Path(__file__).resolve().parents[1]


def _analytics_db() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE runs(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          started_at TEXT NOT NULL,
          distance_km REAL NOT NULL,
          duration_s REAL NOT NULL,
          avg_hr REAL,
          elevation_m REAL,
          rpe REAL
        );
        CREATE TABLE run_samples(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          run_id INTEGER NOT NULL,
          metric_type TEXT NOT NULL,
          sampled_at TEXT NOT NULL,
          value REAL NOT NULL
        );
        CREATE TABLE health_metrics(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          metric_type TEXT NOT NULL,
          start_at TEXT NOT NULL,
          value REAL NOT NULL
        );
        """
    )
    return c


def test_training_trends_aggregate_realistic_weekly_metrics_without_raw_data():
    c = _analytics_db()
    c.execute(
        "INSERT INTO runs(started_at,distance_km,duration_s,avg_hr,elevation_m,rpe) VALUES(?,?,?,?,?,?)",
        ("2026-08-17T07:00:00+02:00", 10.0, 3000.0, 140.0, 90.0, 4.0),
    )
    first = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
    c.execute(
        "INSERT INTO runs(started_at,distance_km,duration_s,avg_hr,elevation_m,rpe) VALUES(?,?,?,?,?,?)",
        ("2026-08-19T07:00:00+02:00", 5.0, 1200.0, 155.0, 30.0, 7.0),
    )
    second = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
    c.execute(
        "INSERT INTO run_samples(run_id,metric_type,sampled_at,value) VALUES(?,?,?,?)",
        (first, "cadence", "2026-08-17T07:00:00+02:00", 164.0),
    )
    c.execute(
        "INSERT INTO run_samples(run_id,metric_type,sampled_at,value) VALUES(?,?,?,?)",
        (second, "cadence", "2026-08-19T07:00:00+02:00", 172.0),
    )
    c.executemany(
        "INSERT INTO health_metrics(metric_type,start_at,value) VALUES(?,?,?)",
        [
            ("resting_hr", "2026-08-18T06:00:00+02:00", 49.0),
            ("hrv_sdnn", "2026-08-18T06:00:00+02:00", 58.0),
            ("sleep_hours", "2026-08-18T06:00:00+02:00", 7.5),
        ],
    )

    result = build_training_trends(c, "3m", today=date(2026, 8, 30))
    week = next(x for x in result["weeks"] if x["week_start"] == "2026-08-17")

    assert week["distance_km"] == 15.0
    assert week["run_count"] == 2
    assert week["longest_run_km"] == 10.0
    assert week["avg_pace_s_per_km"] == 280.0
    assert week["avg_hr"] == 144.3
    assert week["cadence_spm"] == 166.3
    assert week["elevation_m"] == 120.0
    assert week["avg_rpe"] == 5.5
    assert week["resting_hr"] == 49.0
    assert week["hrv_sdnn"] == 58.0
    assert week["sleep_hours"] == 7.5
    assert result["coverage"]["cadence_runs"] == 2
    assert "latitude" not in str(result) and "longitude" not in str(result)


def test_training_trends_reject_invalid_period_and_implausible_cadence():
    c = _analytics_db()
    c.execute(
        "INSERT INTO runs(started_at,distance_km,duration_s) VALUES(?,?,?)",
        ("2026-08-20T07:00:00+02:00", 8.0, 2400.0),
    )
    rid = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
    c.execute(
        "INSERT INTO run_samples(run_id,metric_type,sampled_at,value) VALUES(?,?,?,?)",
        (rid, "cadence", "2026-08-20T07:00:00+02:00", 999.0),
    )
    result = build_training_trends(c, "3m", today=date(2026, 8, 30))
    assert result["coverage"]["cadence_runs"] == 0
    assert all(x["cadence_spm"] is None for x in result["weeks"])

    try:
        build_training_trends(c, "all", today=date(2026, 8, 30))
        assert False, "invalid period must be rejected"
    except ValueError:
        pass


def test_production_security_headers_limits_and_removed_transfer_endpoint(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.headers["x-content-type-options"] == "nosniff"
    assert health.headers["referrer-policy"] == "no-referrer"
    assert "object-src 'none'" in health.headers["content-security-policy"]
    assert "camera=()" in health.headers["permissions-policy"]

    blocked = client.post(
        "/api/runs",
        headers={"Sec-Fetch-Site": "cross-site"},
        json={
            "started_at": "2026-08-30T08:00:00+02:00",
            "distance_km": 5.0,
            "duration_s": 1500,
        },
    )
    assert blocked.status_code == 403

    assert client.post("/api/system/prepare-repository-transfer").status_code in {404, 405}
    assert client.get("/api/coach/history?limit=201").status_code == 422
    assert client.get("/api/progress/trends?period=6m").status_code == 200


def test_release_has_frontend_trends_and_relay_resource_guards():
    index = (ROOT / "laufapp/app/static/index.html").read_text()
    trend_js = (ROOT / "laufapp/app/static/assets/v0213.js").read_text()
    relay = (ROOT / "custom_components/laufapp_hae_relay/__init__.py").read_text()
    cfg = (ROOT / "laufapp/config.yaml").read_text()

    assert "assets/v0213.js?v=0.2.13" in index
    assert "assets/v0213.css?v=0.2.13" in index
    for label in ["Laufkilometer", "Ø Pace", "Kadenz", "HRV (SDNN)", "VO₂max"]:
        assert label in trend_js
    assert "api/progress/trends" in trend_js
    assert "MAX_REQUESTS_PER_MINUTE = 12" in relay
    assert "MAX_CONCURRENT_FORWARDS = 3" in relay
    assert "READ_TIMEOUT_SECONDS = 120" in relay
    assert "asyncio.wait_for" in relay
    assert "share:rw" not in cfg
