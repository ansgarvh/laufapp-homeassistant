from datetime import date
from pathlib import Path

from db import db_conn
from training import refresh_plan, week_start_for


def test_refresh_repairs_duplicate_engine_rows_and_honors_weekly_cap(setup_client):
    assert setup_client.patch('/api/settings', json={
        'max_weekly_km_mode': 'user',
        'max_weekly_km': 75,
        'max_long_run_km': 35,
    }).status_code == 200
    week = setup_client.get('/api/week').json()
    ws = week_start_for(date.today())

    # Reproduce the v0.1.8 failure mode: an earlier refresh could leave an
    # untouched generated row on a date and then create another engine row for
    # exactly the same native training day.
    with db_conn() as c:
        originals = c.execute(
            "SELECT * FROM workouts WHERE origin_week_start=? ORDER BY scheduled_date,id",
            (ws.isoformat(),),
        ).fetchall()
        assert originals
        for row in originals[:2]:
            c.execute(
                "INSERT INTO workouts(week_start,origin_week_start,scheduled_date,workout_type,title,distance_km,pace_low_s_per_km,pace_high_s_per_km,details_json,status,manual_override,modified_by,generation_version) "
                "VALUES(?,?,?,?,?,?,?,?,?,'planned',0,'engine','0.1.8')",
                (row['week_start'], row['origin_week_start'], row['scheduled_date'], row['workout_type'], row['title'], row['distance_km'], row['pace_low_s_per_km'], row['pace_high_s_per_km'], row['details_json']),
            )

        result = refresh_plan(c, ws, 1)
        rows = c.execute(
            "SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id",
            (ws.isoformat(),),
        ).fetchall()
        actual_total = round(sum(float(r['distance_km']) for r in rows), 1)
        dates = [r['scheduled_date'] for r in rows]

    assert actual_total <= 75.1
    assert len(dates) == len(set(dates))
    if 'volume_km' in result['diff']:
        assert result['diff']['volume_km']['new'] == actual_total

    # A second refresh must not grow the week again.
    again = setup_client.post(f'/api/plan/refresh?start={ws.isoformat()}&weeks=1')
    assert again.status_code == 200
    week_after = setup_client.get(f'/api/week?start={ws.isoformat()}').json()
    assert week_after['planned_km'] <= 75.1


def test_refresh_keeps_manual_and_completed_workouts(setup_client):
    week = setup_client.get('/api/week').json()
    ws = week_start_for(date.today())
    first, second = week['workouts'][:2]
    with db_conn() as c:
        c.execute("UPDATE workouts SET status='completed',linked_run_id=NULL WHERE id=?", (first['id'],))
        c.execute("UPDATE workouts SET manual_override=1,modified_by='user' WHERE id=?", (second['id'],))
        protected = {
            r['id']: (r['scheduled_date'], r['distance_km'], r['status'], r['manual_override'])
            for r in c.execute("SELECT * FROM workouts WHERE id IN (?,?)", (first['id'], second['id']))
        }
        refresh_plan(c, ws, 1)
        for wid, expected in protected.items():
            row = c.execute("SELECT * FROM workouts WHERE id=?", (wid,)).fetchone()
            assert row is not None
            assert (row['scheduled_date'], row['distance_km'], row['status'], row['manual_override']) == expected


def test_v019_runtime_and_chart_label_fix_are_loaded():
    root = Path(__file__).resolve().parents[1]
    static = root / 'laufapp' / 'app' / 'static'
    html = (static / 'index.html').read_text()
    runtime = (static / 'runtime-v019.js').read_text()
    css = (static / 'fixes-v019.css').read_text()

    assert 'runtime-v019.js' in html
    assert 'fixes-v019.css' in html
    assert "url.pathname.endsWith('/api/plan/refresh')" in runtime
    assert "start === 'null'" in runtime
    assert 'validationMessage' in runtime
    assert '.chart .chart-bar > span' in css
    assert 'bottom: -20px' in css
