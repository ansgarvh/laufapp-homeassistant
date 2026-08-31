from datetime import date, timedelta
from pathlib import Path

import main_v020  # noqa: F401
import training_v020 as tv
from db import connect, get_setting, init_db, set_setting


def _db(tmp_path: Path):
    path = tmp_path / 'v0218.sqlite3'
    init_db(path)
    return connect(path)


def _add_race(c, name, race_date, priority='A', distance=42.195, goal=12000):
    cur = c.execute(
        "INSERT INTO races(name,distance_km,race_date,goal_seconds,target_source,active) VALUES(?,?,?,?, 'user',1)",
        (name, distance, race_date.isoformat(), goal),
    )
    mapping = dict(get_setting(c, 'race_priorities', {}) or {})
    mapping[str(int(cur.lastrowid))] = priority
    set_setting(c, 'race_priorities', mapping)
    c.commit()
    return int(cur.lastrowid)


def test_two_close_a_races_keep_first_focus_then_recovery_and_switch(tmp_path):
    c = _db(tmp_path)
    try:
        current_ws = tv.base.week_start_for(date.today())
        first_date = current_ws + timedelta(days=4 * 7 + 3)  # Thursday
        second_date = first_date + timedelta(days=19)
        first = _add_race(c, 'A-Marathon', first_date, 'A', 42.195, 12000)
        second = _add_race(c, 'A-Halbmarathon', second_date, 'A', 21.0975, 5700)

        before_ws = tv.base.week_start_for(first_date) - timedelta(days=7)
        before = tv.week_summary(c, before_ws)
        assert before['plan_basis']['focus_race_id'] == first
        assert before['plan_basis']['focus_race_name'] == 'A-Marathon'

        first_week = tv.week_summary(c, tv.base.week_start_for(first_date))
        a_rows = [w for w in first_week['workouts'] if w['details'].get('race_priority') == 'A']
        assert len(a_rows) == 1
        assert a_rows[0]['details']['race_id'] == first

        recovery_ws = tv.base.week_start_for(first_date) + timedelta(days=7)
        recovery = tv.week_summary(c, recovery_ws)
        assert recovery['plan_basis']['focus_race_id'] == second
        assert recovery['plan_basis']['phase'] == 'recovery'
        assert recovery['plan_basis']['previous_a_race']['id'] == first

        transition_ws = recovery_ws + timedelta(days=7)
        transition = tv.week_summary(c, transition_ws)
        assert transition['plan_basis']['focus_race_id'] == second
        assert transition['plan_basis']['phase'] == 'taper'
        assert transition['plan_basis']['previous_a_race']['id'] == first

        second_week = tv.week_summary(c, tv.base.week_start_for(second_date))
        a2 = [w for w in second_week['workouts'] if w['details'].get('race_priority') == 'A']
        assert len(a2) == 1
        assert a2[0]['details']['race_id'] == second
    finally:
        c.close()



def test_later_a_race_does_not_change_weeks_before_earlier_a(tmp_path):
    c = _db(tmp_path)
    try:
        current_ws = tv.base.week_start_for(date.today())
        first_date = current_ws + timedelta(days=8 * 7 + 3)
        before_ws = tv.base.week_start_for(first_date) - timedelta(days=21)
        first = _add_race(c, 'Erstes A-Rennen', first_date, 'A', 42.195, 12000)
        baseline = tv.generate_week(c, before_ws, True)
        baseline_sig = [(w['scheduled_date'], w['workout_type'], w['title'], w['distance_km'], w['details']['plan_basis']['focus_race_id']) for w in baseline]
        assert all(x[-1] == first for x in baseline_sig)

        second_date = first_date + timedelta(days=19)
        _add_race(c, 'Späteres A-Rennen', second_date, 'A', 21.0975, 5700)
        regenerated = tv.generate_week(c, before_ws, True)
        regenerated_sig = [(w['scheduled_date'], w['workout_type'], w['title'], w['distance_km'], w['details']['plan_basis']['focus_race_id']) for w in regenerated]
        assert regenerated_sig == baseline_sig
    finally:
        c.close()

def test_c_race_replaces_quality_but_keeps_longrun(tmp_path):
    c = _db(tmp_path)
    try:
        a_date = tv.base.week_start_for(date.today()) + timedelta(days=10 * 7 + 6)
        _add_race(c, 'A-Marathon', a_date, 'A', 42.195, 12000)
        c_ws = tv.base.week_start_for(date.today()) + timedelta(days=4 * 7)
        c_date = c_ws + timedelta(days=3)
        cid = _add_race(c, 'C-10k', c_date, 'C', 10, 2700)

        week = tv.generate_week(c, c_ws, True)
        c_rows = [w for w in week if w['details'].get('race_priority') == 'C']
        assert len(c_rows) == 1
        assert c_rows[0]['details']['race_id'] == cid
        assert c_rows[0]['scheduled_date'] == c_date.isoformat()
        assert c_rows[0]['details']['replaced_workout_type'] == 'quality'
        assert any(w['workout_type'] == 'long' for w in week)
    finally:
        c.close()


def test_race_api_roundtrips_race_type_and_c_priority(setup_client):
    client = setup_client
    d = (date.today() + timedelta(days=98)).isoformat()
    r = client.post('/api/v2/races', json={
        'name': 'Stadtlauf', 'distance_km': 10.25, 'race_date': d,
        'goal_seconds': 2800, 'priority': 'C', 'race_type': '10k',
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body['priority'] == 'C'
    assert body['race_type'] == '10k'
    assert body['distance_km'] == 10.25
    listed = client.get('/api/v2/races').json()
    stored = next(x for x in listed if x['id'] == body['id'])
    assert stored['priority'] == 'C' and stored['race_type'] == '10k'


def test_race_ui_accepts_german_decimal_and_has_kind_dropdown():
    js = (Path(__file__).resolve().parents[1] / 'laufapp/app/static/assets/v020.js').read_text(encoding='utf-8')
    assert "replace(',', '.')" in js
    assert 'inputmode="decimal"' in js
    assert '<span>Wettkampfart</span>' in js
    for value in ('5k', '10k', 'half_marathon', 'marathon'):
        assert f'value="{value}"' in js
    assert '>A-Rennen<' in js and '>B-Rennen<' in js and '>C-Rennen<' in js
    assert 'race_type:form.race_type.value' in js
