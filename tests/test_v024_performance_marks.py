from datetime import date, timedelta
import sqlite3

import performance_marks_v024 as perf
import training


def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE runs(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          started_at TEXT NOT NULL,
          distance_km REAL NOT NULL,
          duration_s REAL NOT NULL,
          source TEXT NOT NULL DEFAULT 'manual'
        );
        CREATE TABLE performance_marks(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          distance_km REAL NOT NULL,
          duration_s REAL NOT NULL,
          mark_date TEXT NOT NULL,
          source TEXT NOT NULL DEFAULT 'manual',
          label TEXT NOT NULL DEFAULT ''
        );
        """
    )
    return c


def test_detects_half_marathon_from_apple_health_inside_24_months():
    c = conn()
    d = (date.today() - timedelta(days=120)).isoformat()
    c.execute(
        "INSERT INTO runs(started_at,distance_km,duration_s,source) VALUES(?,?,?,?)",
        (d + "T09:00:00+02:00", 21.10, 97 * 60, "apple_health"),
    )
    marks = perf.detect_apple_health_best_efforts(c, training, 24)
    hm = next(x for x in marks if abs(x["distance_km"] - 21.0975) < 0.01)
    assert 96 * 60 < hm["duration_s"] < 98 * 60
    assert hm["source"] == perf.AUTO_SOURCE


def test_sync_preserves_manual_best_time():
    c = conn()
    manual_date = (date.today() - timedelta(days=130)).isoformat()
    health_date = (date.today() - timedelta(days=90)).isoformat()
    c.execute(
        "INSERT INTO performance_marks(distance_km,duration_s,mark_date,source,label) VALUES(?,?,?,?,?)",
        (21.0975, 97 * 60, manual_date, "race", "Frühjahrs-HM"),
    )
    c.execute(
        "INSERT INTO runs(started_at,distance_km,duration_s,source) VALUES(?,?,?,?)",
        (health_date + "T08:00:00+02:00", 21.11, 96.5 * 60, "apple_health"),
    )
    count = perf.sync_apple_health_best_marks(c, training, 24)
    assert count >= 1
    manual = c.execute("SELECT * FROM performance_marks WHERE source='race'").fetchall()
    auto = c.execute("SELECT * FROM performance_marks WHERE source=?", (perf.AUTO_SOURCE,)).fetchall()
    assert len(manual) == 1
    assert any(abs(float(x["distance_km"]) - 21.0975) < 0.01 for x in auto)


def test_old_apple_health_effort_outside_24_months_is_ignored():
    c = conn()
    d = (perf.months_ago(24) - timedelta(days=2)).isoformat()
    c.execute(
        "INSERT INTO runs(started_at,distance_km,duration_s,source) VALUES(?,?,?,?)",
        (d + "T09:00:00+02:00", 21.10, 90 * 60, "apple_health"),
    )
    marks = perf.detect_apple_health_best_efforts(c, training, 24)
    assert not any(abs(x["distance_km"] - 21.0975) < 0.01 for x in marks)


def test_recent_training_can_improve_but_not_replace_confirmed_pb_unchecked(monkeypatch):
    c = conn()
    pb_date = (date.today() - timedelta(days=120)).isoformat()
    fast_date = (date.today() - timedelta(days=10)).isoformat()
    c.execute(
        "INSERT INTO performance_marks(distance_km,duration_s,mark_date,source,label) VALUES(?,?,?,?,?)",
        (21.0975, 97 * 60, pb_date, "race", "Bestzeit"),
    )
    # 10 km in 42:00 is strong recent evidence and should move the HM estimate
    # below the old PB, while the blend prevents a single training run from
    # replacing the confirmed result one-for-one.
    c.execute(
        "INSERT INTO runs(started_at,distance_km,duration_s,source) VALUES(?,?,?,?)",
        (fast_date + "T18:00:00+02:00", 10.0, 42 * 60, "manual"),
    )
    monkeypatch.setattr(training, "weekly_volume", lambda *_a, **_k: [45.0] * 6)
    monkeypatch.setattr(training, "recent_long_runs", lambda *_a, **_k: [24.0])
    pred = perf.predict_distance_v024(c, 21.0975, training)
    assert pred is not None
    assert pred["predicted_seconds"] < 97 * 60
    assert pred["performance_anchor"]["source"] == "race"
    assert pred["improvement_since_best_seconds"] > 0
