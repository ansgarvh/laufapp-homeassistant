from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import main_v0218  # noqa: F401 - activates the full release stack
import training_v020 as tv
from db import connect, get_setting, init_db, set_setting


def _db(tmp_path: Path):
    path = tmp_path / "v0218.sqlite3"
    init_db(path)
    return connect(path)


def _insert_race(c, name, race_date, priority, distance=42.195, goal=12000):
    cur = c.execute(
        "INSERT INTO races(name,distance_km,race_date,goal_seconds,target_source,active) "
        "VALUES(?,?,?,?, 'user',1)",
        (name, distance, race_date.isoformat(), goal),
    )
    rid = int(cur.lastrowid)
    mapping = dict(get_setting(c, "race_priorities", {}) or {})
    mapping[str(rid)] = priority
    set_setting(c, "race_priorities", mapping)
    c.commit()
    return rid


def _row_signature(c, cutoff: date):
    rows = c.execute(
        "SELECT id,week_start,origin_week_start,scheduled_date,workout_type,title,distance_km," \
        "status,linked_run_id,manual_override,modified_by,details_json FROM workouts "
        "WHERE scheduled_date<? ORDER BY id",
        (cutoff.isoformat(),),
    ).fetchall()
    return [tuple(r) for r in rows]


def test_two_a_races_are_owned_chronologically_and_marathon_recovery_precedes_second(tmp_path):
    c = _db(tmp_path)
    try:
        current_ws = tv.base.week_start_for(date.today())
        marathon_ws = current_ws + timedelta(days=5 * 7)
        marathon_date = marathon_ws + timedelta(days=3)  # Thursday
        hm_date = marathon_date + timedelta(days=19)
        marathon = _insert_race(c, "A-Marathon", marathon_date, "A", 42.195, 12000)
        hm = _insert_race(c, "A-Halbmarathon", hm_date, "A", 21.0975, 5700)

        assert int(tv.race_for_week(c, marathon_ws - timedelta(days=7))["id"]) == marathon
        assert int(tv.race_for_week(c, marathon_ws)["id"]) == marathon

        post_ws = marathon_ws + timedelta(days=7)
        assert int(tv.race_for_week(c, post_ws)["id"]) == hm
        transition = tv._race_transition(c, post_ws, tv.race_for_week(c, post_ws))
        assert transition and transition["mode"] == "post_a_recovery"
        assert transition["easy_only"] is True

        workouts = tv.generate_week(c, post_ws, True)
        assert 2 <= len(workouts) <= 3
        assert all(w["workout_type"] == "easy" for w in workouts)
        basis = workouts[0]["details"]["plan_basis"]
        assert basis["focus_race_id"] == hm
        assert basis["race_transition"]["previous_race_id"] == marathon
        assert basis["race_transition"]["mode"] == "post_a_recovery"

        reentry_ws = marathon_ws + timedelta(days=14)
        assert int(tv.race_for_week(c, reentry_ws)["id"]) == hm
        reentry = tv._race_transition(c, reentry_ws, tv.race_for_week(c, reentry_ws))
        assert reentry and reentry["mode"] == "post_a_reentry" and reentry["phase"] == "taper"
        reentry_workouts = tv.generate_week(c, reentry_ws, True)
        assert reentry_workouts and any(w["workout_type"] != "easy" for w in reentry_workouts)

        hm_ws = tv.base.week_start_for(hm_date)
        hm_workouts = tv.generate_week(c, hm_ws, True)
        hm_races = [w for w in hm_workouts if w["workout_type"] == "race" and w["details"].get("race_priority") == "A"]
        assert len(hm_races) == 1 and hm_races[0]["scheduled_date"] == hm_date.isoformat()
        assert abs(float(hm_races[0]["distance_km"]) - 21.0975) < 0.05
    finally:
        c.close()


def test_later_a_race_does_not_influence_weeks_before_earlier_a(tmp_path):
    c = _db(tmp_path)
    try:
        ws = tv.base.week_start_for(date.today()) + timedelta(days=3 * 7)
        first_date = ws + timedelta(days=6)
        second_date = first_date + timedelta(days=35)
        first = _insert_race(c, "Erstes A", first_date, "A", 42.195, 12100)
        second = _insert_race(c, "Späteres A", second_date, "A", 21.0975, 5800)

        race = tv.race_for_week(c, ws - timedelta(days=14))
        assert int(race["id"]) == first
        total, phase = tv._weekly_target(c, race, ws - timedelta(days=14))
        basis = tv.plan_basis(c, ws - timedelta(days=14), race, total, phase)
        assert basis["focus_race_id"] == first
        assert basis["focus_race_id"] != second
    finally:
        c.close()


def test_c_race_is_local_training_race_and_does_not_take_a_focus(tmp_path):
    c = _db(tmp_path)
    try:
        current_ws = tv.base.week_start_for(date.today())
        a_date = current_ws + timedelta(days=10 * 7 + 6)
        a_id = _insert_race(c, "A-Marathon", a_date, "A", 42.195, 12000)
        c_ws = current_ws + timedelta(days=3 * 7)
        c_date = c_ws + timedelta(days=5)
        c_id = _insert_race(c, "C-10k", c_date, "C", 10.0, 2700)

        assert tv.race_priority(c, c_id) == "C"
        assert int(tv.race_for_week(c, c_ws)["id"]) == a_id
        workouts = tv.generate_week(c, c_ws, True)
        races = [w for w in workouts if w["workout_type"] == "race"]
        assert len(races) == 1
        assert races[0]["scheduled_date"] == c_date.isoformat()
        assert races[0]["details"]["race_priority"] == "C"
        assert races[0]["details"]["plan_basis"]["focus_race_id"] == a_id
    finally:
        c.close()


def test_refresh_requested_entirely_in_past_is_noop(tmp_path):
    c = _db(tmp_path)
    try:
        past_ws = tv.base.week_start_for(date.today()) - timedelta(days=14)
        c.execute(
            "INSERT INTO workouts(week_start,origin_week_start,scheduled_date,workout_type,title,distance_km," \
            "details_json,status,manual_override,modified_by,generation_version) "
            "VALUES(?,?,?,?,?,?,'{}','planned',0,'engine','historic')",
            (past_ws.isoformat(), past_ws.isoformat(), (past_ws + timedelta(days=1)).isoformat(), "easy", "HISTORISCH", 7.7),
        )
        c.commit()
        before = _row_signature(c, date.today())
        result = tv.refresh_plan(c, past_ws, 1)
        after = _row_signature(c, date.today())
        assert result["weeks"] == 0
        assert result["past_protected"] is True
        assert after == before
    finally:
        c.close()


def test_adding_a_race_through_api_never_changes_rows_before_today(setup_client):
    client = setup_client
    from db import db_conn

    today = date.today()
    historic_day = today - timedelta(days=9)
    historic_ws = tv.base.week_start_for(historic_day)
    with db_conn() as c:
        c.execute(
            "INSERT INTO workouts(week_start,origin_week_start,scheduled_date,workout_type,title,distance_km," \
            "details_json,status,manual_override,modified_by,generation_version) "
            "VALUES(?,?,?,?,?,?,'{}','completed',1,'user','historic')",
            (historic_ws.isoformat(), historic_ws.isoformat(), historic_day.isoformat(), "easy", "Unveränderbare Vergangenheit", 8.8),
        )
        before = _row_signature(c, today)

    new_date = today + timedelta(days=31)
    response = client.post(
        "/api/v2/races",
        json={"name":"Neues A-Rennen","distance_km":42.195,"race_date":new_date.isoformat(),"goal_seconds":11900,"priority":"A"},
    )
    assert response.status_code == 201, response.text

    with db_conn() as c:
        after = _row_signature(c, today)
    assert after == before


def test_race_api_accepts_c_and_returns_calendar_priority(setup_client):
    client = setup_client
    race_date = (date.today() + timedelta(days=43)).isoformat()
    response = client.post(
        "/api/v2/races",
        json={"name":"C-Testlauf","distance_km":10,"race_date":race_date,"goal_seconds":2700,"priority":"C"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["priority"] == "C"
    listed = client.get("/api/v2/races").json()
    assert any(r["name"] == "C-Testlauf" and r["priority"] == "C" for r in listed)
