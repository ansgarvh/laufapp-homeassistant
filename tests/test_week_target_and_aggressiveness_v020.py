from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import main_v020  # noqa: F401 - activates v0.2 runtime wiring/guardrails
import training as base
import training_v020 as training
from db import connect, init_db, set_setting

ROOT = Path(__file__).resolve().parents[1]


def _db(tmp_path: Path, name: str):
    path = tmp_path / name
    init_db(path)
    return connect(path)


def _race(c, ws: date, weeks_to_race: int = 4):
    race_date = ws + timedelta(days=weeks_to_race * 7 + 6)
    cur = c.execute(
        "INSERT INTO races(name,distance_km,race_date,goal_seconds,target_source,active) "
        "VALUES('Marathon',42.195,?,12000,'user',1)",
        (race_date.isoformat(),),
    )
    rid = int(cur.lastrowid)
    set_setting(c, "race_priorities", {str(rid): "A"})
    c.commit()
    return c.execute("SELECT * FROM races WHERE id=?", (rid,)).fetchone()


def _seed_user_like_history(c, ws: date, weekly_km: float = 60.9, long_km: float = 32.0, weeks: int = 6):
    remaining = weekly_km - long_km
    other = [round(remaining / 3, 1), round(remaining / 3, 1)]
    other.append(round(remaining - sum(other), 1))
    for n in range(weeks, 0, -1):
        hist = ws - timedelta(days=n * 7)
        distances = [other[0], other[1], other[2], long_km]
        for i, (dow, km) in enumerate(zip((1, 3, 4, 6), distances)):
            d = hist + timedelta(days=dow)
            c.execute(
                "INSERT INTO runs(external_id,started_at,distance_km,duration_s,source,rpe) "
                "VALUES(?,?,?,?, 'manual',3)",
                (f"history-{n}-{i}", f"{d.isoformat()}T07:00:00+02:00", km, km * 330),
            )
    c.commit()


def _configure(c):
    set_setting(c, "training_days", [1, 3, 4, 6])
    set_setting(c, "quality_sessions_per_week", 2)
    set_setting(c, "max_weekly_km_mode", "user")
    set_setting(c, "max_weekly_km", 75.0)
    set_setting(c, "max_long_run_km", 35.0)
    set_setting(c, "max_long_run_share", 0.45)
    set_setting(c, "training_volume_profile", "steady")
    c.commit()


def test_user_like_specific_week_hits_weekly_target_instead_of_post_guardrail_shortfall(tmp_path):
    """Regression for the 60.9 basis / 63.3 target / 57.6 displayed week issue."""
    ws = base.week_start_for(date.today()) + timedelta(days=7)
    c = _db(tmp_path, "weekly-target.sqlite3")
    _configure(c)
    _seed_user_like_history(c, ws)
    race = _race(c, ws, 4)

    target, phase = training._weekly_target(c, race, ws)
    workouts = training.generate_week(c, ws, True)
    planned = round(sum(float(w["distance_km"]) for w in workouts), 1)
    long_km = max(float(w["distance_km"]) for w in workouts if w["workout_type"] == "long")

    assert phase == "specific"
    assert 63.0 <= target <= 64.0
    assert abs(planned - target) <= 0.4, (target, planned, workouts)
    assert long_km >= 30.0, "Recent tolerated 32 km Long Runs must not be post-hoc cut to ~26 km by the default share orientation."
    c.close()


def test_strict_longrun_share_redistributes_removed_km_to_easy_volume(tmp_path):
    """A deliberately strict share may shorten the Long Run but must not silently erase the weekly target."""
    ws = base.week_start_for(date.today()) + timedelta(days=7)
    c = _db(tmp_path, "strict-share.sqlite3")
    _configure(c)
    set_setting(c, "max_long_run_share", 0.40)
    _seed_user_like_history(c, ws)
    race = _race(c, ws, 4)

    target, _ = training._weekly_target(c, race, ws)
    workouts = training.generate_week(c, ws, True)
    planned = round(sum(float(w["distance_km"]) for w in workouts), 1)
    long_run = next(w for w in workouts if w["workout_type"] == "long")

    assert abs(planned - target) <= 0.5, (target, planned, workouts)
    assert float(long_run["distance_km"]) / planned <= 0.405
    assert any(float((w.get("details") or {}).get("guardrail_redistributed_km", 0) or 0) > 0 for w in workouts if w["workout_type"] == "easy")
    c.close()


def test_planner_aggressiveness_orders_progression_but_never_overrides_user_cap(tmp_path):
    ws = base.week_start_for(date.today()) + timedelta(days=7)
    c = _db(tmp_path, "aggressiveness.sqlite3")
    _configure(c)
    _seed_user_like_history(c, ws)
    race = _race(c, ws, 4)

    targets = {}
    for profile in ("gradual", "steady", "progressive"):
        set_setting(c, "training_volume_profile", profile)
        targets[profile] = training._weekly_target(c, race, ws)[0]
    assert targets["gradual"] < targets["steady"] < targets["progressive"], targets

    set_setting(c, "max_weekly_km", 61.5)
    set_setting(c, "training_volume_profile", "progressive")
    assert training._weekly_target(c, race, ws)[0] <= 61.5
    c.close()


def test_settings_ui_exposes_three_aggressiveness_levels_and_clear_plan_basis_labels():
    js = (ROOT / "laufapp" / "app" / "static" / "assets" / "v020_science.js").read_text(encoding="utf-8")
    assert "Planungsaggressivität" in js
    assert ">Konservativ<" in js
    assert ">Moderat<" in js
    assert ">Aggressiv<" in js
    assert "training_volume_profile" in js
    assert "Trainingsbasis" in js
    assert "Wochenziel" in js
