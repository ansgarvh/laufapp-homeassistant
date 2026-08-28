from datetime import date,timedelta
from db import db_conn
from training import established_volume,long_run_history,week_start_for

def add_week(c,ws,total,long):
    others=(total-long)/3
    for i,km in zip((0,2,4,6),(others,others,others,long)):
        d=ws+timedelta(days=i)
        c.execute("INSERT INTO runs(external_id,started_at,distance_km,duration_s,source) VALUES(?,?,?,?, 'apple_health')",(f'{d}-{km}',d.isoformat()+'T08:00:00+00:00',km,km*330))

def test_partial_week_does_not_suppress_established_volume(setup_client):
    current=week_start_for(date.today())
    with db_conn() as c:
        for n,total in enumerate((64,66,68),3):add_week(c,current-timedelta(days=7*n),total,24+n)
        c.execute("INSERT INTO runs(external_id,started_at,distance_km,duration_s) VALUES('partial',?,?,6000)",(date.today().isoformat()+'T06:00:00+00:00',18))
        result=established_volume(c)
    assert result['km']>=63 and result['current_partial_km']==18

def test_completed_decline_is_detraining(setup_client):
    current=week_start_for(date.today())
    with db_conn() as c:
        for n,total in enumerate((65,62,42,30,24)):add_week(c,current-timedelta(days=7*(5-n)),total,min(24,total*.35))
        result=established_volume(c)
    assert result['trend']=='reduziert' and result['km']<50

def test_health_history_marks_stale_then_refresh_preserves_manual(setup_client):
    before=setup_client.get('/api/week').json(); wid=before['workouts'][0]['id']; chosen=before['workouts'][1]['scheduled_date']
    assert setup_client.post(f'/api/workouts/{wid}/move',json={'scheduled_date':chosen}).status_code==200
    with db_conn() as c:
        current=week_start_for(date.today())
        for n,total in enumerate((61,67,64,69),4):add_week(c,current-timedelta(days=7*n),total,24+n)
        from training import mark_plan_stale
        mark_plan_stale(c,'Neue Apple-Health-Läufe verfügbar')
    stale=setup_client.get('/api/week').json(); assert stale['plan_stale'] is True
    assert setup_client.post('/api/plan/refresh?weeks=4').status_code==200
    after=setup_client.get('/api/week').json(); moved=next(x for x in after['workouts'] if x['id']==wid)
    assert after['plan_stale'] is False and moved['scheduled_date']==chosen and moved['manual_override']==1
    assert after['plan_basis']['established_weekly_km']>55

def test_peak_long_run_available_only_with_history_and_limit(setup_client):
    current=week_start_for(date.today())
    with db_conn() as c:
        race=(current+timedelta(days=7*4)).isoformat();c.execute("UPDATE races SET race_date=?",(race,))
        for n,total in enumerate((62,66,68,65,67),5):add_week(c,current-timedelta(days=7*n),total,28+(n%3))
    setup_client.patch('/api/settings',json={'max_long_run_km':34})
    setup_client.post('/api/plan/refresh?weeks=1')
    week=setup_client.get('/api/week').json(); lr=next(x for x in week['workouts'] if x['workout_type']=='long')
    assert 30<=lr['distance_km']<=34
