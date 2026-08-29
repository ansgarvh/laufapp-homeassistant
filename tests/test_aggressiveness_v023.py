from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import main_v023  # noqa: F401 - activates v0.2.3 runtime overlay
import training as base
import training_v020 as training
from db import connect, get_setting, init_db, set_setting


def _db(tmp_path: Path):
    path = tmp_path / "aggressiveness.sqlite3"
    init_db(path)
    return connect(path)


def _seed_weekly_runs(c, start: date, weekly: float = 60.0, weeks: int = 6):
    shares = (.22, .20, .18, .40)
    days = (1, 3, 4, 6)
    for n in range(weeks, 0, -1):
        ws = start - timedelta(days=n * 7)
        for i, (dow, share) in enumerate(zip(days, shares)):
            km = round(weekly * share, 1)
            d = ws + timedelta(days=dow)
            c.execute(
                "INSERT INTO runs(external_id,started_at,distance_km,duration_s,source,rpe) VALUES(?,?,?,?, 'manual',3)",
                (f"hist-{n}-{i}", f"{d.isoformat()}T07:00:00+02:00", km, km * 330),
            )
    c.commit()


def _race(c, ws: date, weeks: int):
    rd = ws + timedelta(days=weeks * 7 + 6)
    cur = c.execute(
        "INSERT INTO races(name,distance_km,race_date,goal_seconds,target_source,active) VALUES('Marathon',42.195,?,?,'user',1)",
        (rd.isoformat(), 3 * 3600 + 20 * 60),
    )
    rid = int(cur.lastrowid)
    set_setting(c, "race_priorities", {str(rid): "A"})
    c.commit()
    return c.execute("SELECT * FROM races WHERE id=?", (rid,)).fetchone()


def test_very_aggressive_adds_about_2_5_percent_to_loading_week(tmp_path):
    c = _db(tmp_path)
    ws = base.week_start_for(date.today()) + timedelta(days=7)
    _seed_weekly_runs(c, ws, 60.0)
    race = _race(c, ws, 10)  # Build, load position 3
    set_setting(c, "max_weekly_km_mode", "user")
    set_setting(c, "max_weekly_km", 120.0)
    set_setting(c, "training_volume_profile", "progressive")
    set_setting(c, "training_volume_boost_pct", 0.0)
    c.commit()

    aggressive, phase_a = training._weekly_target(c, race, ws)
    set_setting(c, "training_volume_boost_pct", 0.025)
    c.commit()
    very_aggressive, phase_v = training._weekly_target(c, race, ws)

    assert phase_a == phase_v == "build"
    assert very_aggressive == round(aggressive * 1.025, 1)
    assert very_aggressive > aggressive
    c.close()


def test_very_aggressive_does_not_boost_taper_or_break_user_cap(tmp_path):
    c = _db(tmp_path)
    ws = base.week_start_for(date.today()) + timedelta(days=7)
    _seed_weekly_runs(c, ws, 60.0)
    race = _race(c, ws, 2)
    set_setting(c, "training_volume_profile", "progressive")
    set_setting(c, "max_weekly_km_mode", "user")
    set_setting(c, "max_weekly_km", 61.0)
    set_setting(c, "training_volume_boost_pct", 0.0)
    c.commit()
    aggressive, phase_a = training._weekly_target(c, race, ws)

    set_setting(c, "training_volume_boost_pct", 0.025)
    c.commit()
    very_aggressive, phase_v = training._weekly_target(c, race, ws)

    assert phase_a == phase_v == "taper"
    assert very_aggressive == aggressive
    assert very_aggressive <= 61.0
    c.close()


def test_aggressiveness_api_is_backward_compatible_and_persistent(setup_client):
    client = setup_client
    r = client.patch(
        "/api/v2/settings/aggressiveness",
        json={"training_volume_profile": "very_progressive"},
    )
    assert r.status_code == 200, r.text

    semantic = client.get("/api/v2/settings/aggressiveness")
    assert semantic.status_code == 200
    assert semantic.json()["training_volume_profile"] == "very_progressive"
    assert semantic.json()["extra_weekly_target_pct"] == 2.5

    settings = client.get("/api/settings").json()
    assert settings["training_aggressiveness_level"] == "very_progressive"
    assert settings["training_volume_profile"] == "progressive"
    assert settings["training_volume_boost_pct"] == 2.5
    assert settings["plan_stale"] is True

    with main_v023.db_conn() as c:
        assert get_setting(c, "training_volume_profile") == "progressive"
        assert float(get_setting(c, "training_volume_boost_pct")) == 0.025

    back = client.patch(
        "/api/v2/settings/aggressiveness",
        json={"training_volume_profile": "steady"},
    )
    assert back.status_code == 200
    assert client.get("/api/v2/settings/aggressiveness").json()["training_volume_profile"] == "steady"
