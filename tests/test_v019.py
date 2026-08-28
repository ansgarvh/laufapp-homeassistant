from datetime import date

from db import db_conn
from training import week_start_for


def test_plan_refresh_from_settings_without_week_state(setup_client):
    """Frontend v0.1.8 sends start=null when settings is opened before Woche."""
    r=setup_client.post('/api/plan/refresh?start=null&weeks=4')
    assert r.status_code==200, r.text
    body=r.json()
    assert body['summary_week_start']==week_start_for(date.today()).isoformat()


def test_week_open_repairs_generated_duplicate_on_completed_date(setup_client):
    before=setup_client.get('/api/week').json()
    original=before['workouts'][0]
    assert setup_client.post(f"/api/workouts/{original['id']}/status",json={'status':'completed'}).status_code==200

    with db_conn() as c:
        c.execute(
            "INSERT INTO workouts(week_start,origin_week_start,scheduled_date,workout_type,title,distance_km,details_json,status,manual_override,modified_by,generation_version) "
            "VALUES(?,?,?,?,?,8.7,'{}','planned',0,'engine','0.1.8')",
            (before['week_start'],before['week_start'],original['scheduled_date'],'easy','Stale duplicate'),
        )
        assert c.execute("SELECT COUNT(*) n FROM workouts WHERE scheduled_date=?",(original['scheduled_date'],)).fetchone()['n']==2

    repaired=setup_client.get(f"/api/week?start={before['week_start']}").json()
    same_day=[w for w in repaired['workouts'] if w['scheduled_date']==original['scheduled_date']]
    assert len(same_day)==1
    assert same_day[0]['id']==original['id']
    assert same_day[0]['status']=='completed'


def test_refresh_respects_caps_and_does_not_duplicate_protected_days(setup_client):
    assert setup_client.patch('/api/settings',json={
        'max_weekly_km_mode':'user',
        'max_weekly_km':75,
        'max_long_run_km':35,
    }).status_code==200
    before=setup_client.get('/api/week').json()
    protected=before['workouts'][1:3]
    for w in protected:
        assert setup_client.post(f"/api/workouts/{w['id']}/status",json={'status':'completed'}).status_code==200

    r=setup_client.post(f"/api/plan/refresh?start={before['week_start']}&weeks=1")
    assert r.status_code==200, r.text
    after=setup_client.get(f"/api/week?start={before['week_start']}").json()

    dates=[w['scheduled_date'] for w in after['workouts']]
    assert len(dates)==len(set(dates))
    assert after['planned_km']<=75.1
    longruns=[w['distance_km'] for w in after['workouts'] if w['workout_type']=='long']
    assert not longruns or max(longruns)<=35
    for old in protected:
        kept=next(w for w in after['workouts'] if w['id']==old['id'])
        assert kept['status']=='completed'


def test_v019_ui_regressions_are_styled():
    index=open('laufapp/app/static/index.html').read()
    css=open('laufapp/app/static/bugfix.css').read()
    assert 'assets/bugfix.css' in index
    assert '.chart .chart-bar > span' in css
    assert 'bottom:-20px' in css.replace(' ','')
    assert 'grid-template-columns:30px 45px minmax(0,1fr) 36px' in css
    assert ':not(:has(.drag-handle))::before' in css
