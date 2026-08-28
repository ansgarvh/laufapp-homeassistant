from datetime import date,timedelta
from db import db_conn
from training import refresh_plan,week_start_for


def test_defaults_and_settings_persist(setup_client):
    s=setup_client.get('/api/settings').json()
    assert s['running_days_per_week']==4 and s['quality_sessions_per_week']==2
    assert s['max_weekly_km_mode']=='auto' and s['recommended_max_weekly_km']>0
    r=setup_client.patch('/api/settings',json={'training_days':[0,1,3,4,6],'quality_sessions_per_week':2,'max_weekly_km_mode':'user','max_weekly_km':45,'max_long_run_km':28})
    assert r.status_code==200
    s=setup_client.get('/api/settings').json();assert s['training_days']==[0,1,3,4,6] and s['max_weekly_km']==45 and s['max_long_run_km']==28 and s['plan_stale']


def test_variable_days_constraints_and_auto_return(setup_client):
    for days in ([1,3,6],[0,1,3,4,6],[0,1,2,3,4,6],[0,1,2,3,4,5,6]):
        q=min(2,len(days)-2)
        assert setup_client.patch('/api/settings',json={'training_days':days,'quality_sessions_per_week':q,'max_weekly_km_mode':'user','max_weekly_km':40,'max_long_run_km':18}).status_code==200
        target=(week_start_for(date.today())+timedelta(days=7)).isoformat()
        assert setup_client.post(f'/api/plan/refresh?start={target}&weeks=1').status_code==200
        w=setup_client.get(f'/api/week?start={target}').json();native=[x for x in w['workouts'] if x['origin_week_start']==w['week_start']]
        assert len(native)==len(days) and sum(x['distance_km'] for x in native)<=40.1
        assert max(x['distance_km'] for x in native if x['workout_type']=='long')<=18
        assert sum(x['workout_type']=='quality' for x in native)+sum(x['workout_type']=='long' and x['details'].get('rpe_target')=='6/10' for x in native)<=q
    r=setup_client.patch('/api/settings',json={'max_weekly_km_mode':'auto'}).json();assert r['max_weekly_km_mode']=='auto' and r['plan_stale']


def test_unsafe_quality_rejected(setup_client):
    r=setup_client.patch('/api/settings',json={'training_days':[1,3,6],'quality_sessions_per_week':3})
    assert r.status_code==422 and 'Mindestens zwei Lauftage' in r.text


def test_refresh_diff_is_exactly_one_calendar_week(setup_client):
    ws=week_start_for(date.today())
    with db_conn() as c:
        # Inflate other future weeks: they must not enter the singular Wochenumfang.
        for n in (1,2,3):
            future=(ws+timedelta(days=7*n)).isoformat()
            c.execute("INSERT INTO workouts(week_start,origin_week_start,scheduled_date,workout_type,title,distance_km,details_json,status,manual_override,modified_by) VALUES(?,?,?,?,?,60,'{}','planned',1,'user')",(future,future,future,'easy','Protected'))
        old=sum(float(x['distance_km']) for x in c.execute('SELECT distance_km FROM workouts WHERE week_start=?',(ws.isoformat(),)))
        result=refresh_plan(c,ws,4)
        new=sum(float(x['distance_km']) for x in c.execute('SELECT distance_km FROM workouts WHERE week_start=?',(ws.isoformat(),)))
    assert result['summary_week_start']==ws.isoformat()
    if 'volume_km' in result['diff']:
        assert result['diff']['volume_km']=={'old':round(old,1),'new':round(new,1)}
        assert result['diff']['volume_km']['new']<150


def test_current_week_static_navigation():
    js=open('laufapp/app/static/app.js').read();html=open('laufapp/app/static/index.html').read()
    assert 'Aktuelle Woche' in js and "state.weekRequest" in js and "case'settings'" in js
    assert '<small>Einstellungen</small>' in html and 'repeat(6' in open('laufapp/app/static/styles.css').read()
