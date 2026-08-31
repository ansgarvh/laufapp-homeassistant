from datetime import date, timedelta
from pathlib import Path

import main_v020  # noqa: F401 - registers/patches the v0.2 API before fixtures run
import training_v020 as tv
from db import connect, get_setting, init_db, set_setting


def _db(tmp_path: Path):
    path=tmp_path/'v020.sqlite3';init_db(path);return connect(path)


def _race(c,name,days,priority='A',distance=42.195,goal=12000):
    d=date.today()+timedelta(days=days)
    cur=c.execute("INSERT INTO races(name,distance_km,race_date,goal_seconds,target_source,active) VALUES(?,?,?,?, 'user',1)",(name,distance,d.isoformat(),goal))
    mapping=dict(get_setting(c,'race_priorities',{}) or {})
    mapping[str(int(cur.lastrowid))]=priority;set_setting(c,'race_priorities',mapping);c.commit();return int(cur.lastrowid),d


def test_multiple_a_races_switch_focus_after_first(tmp_path):
    c=_db(tmp_path)
    try:
        first,d1=_race(c,'Frühjahrs-A',35,'A')
        second,_=_race(c,'Herbst-A',140,'A')
        assert int(tv.current_race(c)['id'])==first
        # The first A-race owns its entire race week. The following Monday starts
        # the next block and therefore hands focus to the next A-race.
        ws_after_first=tv.base.week_start_for(d1)+timedelta(days=7)
        assert int(tv.race_for_week(c,ws_after_first)['id'])==second
    finally:c.close()


def test_b_race_replaces_longrun_only_in_its_week(tmp_path):
    c=_db(tmp_path)
    try:
        a_id,_=_race(c,'A-Marathon',70,'A')
        ws=tv.base.week_start_for(date.today()+timedelta(days=14))
        b_date=ws+timedelta(days=6)
        cur=c.execute("INSERT INTO races(name,distance_km,race_date,goal_seconds,target_source,active) VALUES('Test 10k',10,?,2700,'user',1)",(b_date.isoformat(),))
        set_setting(c,'race_priorities',{str(int(cur.lastrowid)):'B',str(a_id):'A'})
        c.commit()
        workouts=tv.generate_week(c,ws,True)
        assert len(workouts)==4
        races=[w for w in workouts if w['workout_type']=='race']
        assert len(races)==1 and races[0]['scheduled_date']==b_date.isoformat()
        assert races[0]['distance_km']==10
        assert races[0]['details']['race_priority']=='B'
        assert not [w for w in workouts if w['workout_type']=='long']
        assert len([w for w in workouts if w['workout_type']!='race'])==3
    finally:c.close()


def test_two_consecutive_specific_load_weeks_progress(tmp_path):
    c=_db(tmp_path)
    try:
        race_ws=tv.base.week_start_for(date.today())+timedelta(days=8*7)
        race_date=race_ws+timedelta(days=6)
        cur=c.execute("INSERT INTO races(name,distance_km,race_date,goal_seconds,target_source,active) VALUES('A',42.195,?,12000,'user',1)",(race_date.isoformat(),))
        rid=int(cur.lastrowid)
        set_setting(c,'race_priorities',{str(rid):'A'});set_setting(c,'training_volume_profile','steady');c.commit()
        r=c.execute("SELECT * FROM races WHERE id=?",(rid,)).fetchone()
        ws1=race_ws-timedelta(days=8*7);ws2=ws1+timedelta(days=7)
        t1,p1=tv._weekly_target(c,r,ws1);t2,p2=tv._weekly_target(c,r,ws2)
        assert p1=='specific' and p2=='specific'
        assert t2>t1
    finally:c.close()


def test_race_api_supports_a_b_and_recommendation(setup_client):
    client=setup_client
    d=(date.today()+timedelta(days=91)).isoformat()
    r=client.post('/api/v2/races',json={'name':'B-Halbmarathon','distance_km':21.0975,'race_date':d,'goal_seconds':6000,'priority':'B'})
    assert r.status_code==201,r.text
    assert r.json()['priority']=='B'
    listed=client.get('/api/v2/races');assert listed.status_code==200
    assert any(x['name']=='B-Halbmarathon' and x['priority']=='B' for x in listed.json())
    rec=client.get('/api/v2/races/recommendation?distance_km=10');assert rec.status_code==200
    assert 'available' in rec.json()


def test_b_race_api_does_not_recalculate_preceding_weeks(setup_client):
    client=setup_client
    current=client.get('/api/week').json()
    before=[(w['id'],w['scheduled_date'],w['title'],w['distance_km']) for w in current['workouts']]
    assert client.get('/api/settings').json()['plan_stale'] is False

    b_ws=tv.base.week_start_for(date.today()+timedelta(days=35))
    b_date=b_ws+timedelta(days=6)
    created=client.post('/api/v2/races',json={'name':'Lokales B-Rennen','distance_km':10,'race_date':b_date.isoformat(),'goal_seconds':2700,'priority':'B'})
    assert created.status_code==201,created.text

    # B-race changes are deliberately local: no global stale state and no change
    # to the already generated current week.
    assert client.get('/api/settings').json()['plan_stale'] is False
    after_week=client.get('/api/week').json()
    after=[(w['id'],w['scheduled_date'],w['title'],w['distance_km']) for w in after_week['workouts']]
    assert after==before

    race_week=client.get(f"/api/week?start={b_ws.isoformat()}").json()
    b_workouts=[w for w in race_week['workouts'] if w['workout_type']=='race' and w['details'].get('race_priority')=='B']
    assert len(b_workouts)==1
    assert b_workouts[0]['scheduled_date']==b_date.isoformat()
    assert not [w for w in race_week['workouts'] if w['workout_type']=='long']

    # Removing the B-race restores that week without touching earlier weeks.
    deleted=client.delete(f"/api/v2/races/{created.json()['id']}");assert deleted.status_code==200
    restored=client.get(f"/api/week?start={b_ws.isoformat()}").json()
    assert len([w for w in restored['workouts'] if w['workout_type']=='long'])==1
    assert not [w for w in restored['workouts'] if w['details'].get('race_priority')=='B']


def test_completed_workout_can_assign_shoe_and_increase_shoe_km(setup_client):
    client=setup_client
    shoe=client.post('/api/shoes',json={'brand':'Test','model':'Trainer','nickname':'Daily','start_km':5}).json()['id']
    week=client.get('/api/week').json();w=week['workouts'][0]
    run=client.post('/api/runs',json={'started_at':f"{w['scheduled_date']}T08:00:00+02:00",'distance_km':w['distance_km'],'duration_s':3600,'source':'manual'})
    assert run.status_code==200,run.text
    info=client.get(f"/api/v2/workouts/{w['id']}/run-info");assert info.status_code==200
    assert info.json()['workout']['status']=='completed'
    assigned=client.patch(f"/api/v2/workouts/{w['id']}/shoe",json={'shoe_id':shoe});assert assigned.status_code==200,assigned.text
    shoes=client.get('/api/shoes').json();row=next(x for x in shoes if x['id']==shoe)
    assert row['total_km']>=5+float(w['distance_km'])-.05


def test_v020_synthetic_end_to_end(setup_client):
    """Full v0.2 user flow across races, plan generation, run and shoe data."""
    client=setup_client
    # Add a second A-race and a B-race between both A targets.
    a2_date=(date.today()+timedelta(days=154)).isoformat()
    a2=client.post('/api/v2/races',json={'name':'Zweites A-Rennen','distance_km':42.195,'race_date':a2_date,'goal_seconds':11800,'priority':'A'})
    assert a2.status_code==201,a2.text
    assert client.get('/api/settings').json()['plan_stale'] is False

    # A-race calendar changes now re-align already generated future weeks
    # immediately; historical dates remain protected by the planner itself.
    refreshed=client.post('/api/plan/refresh?weeks=4')
    assert refreshed.status_code==200,refreshed.text
    assert refreshed.json().get('past_protected') is True
    assert client.get('/api/settings').json()['plan_stale'] is False

    b_ws=tv.base.week_start_for(date.today()+timedelta(days=42))
    b_date=b_ws+timedelta(days=6)
    b=client.post('/api/v2/races',json={'name':'10-km-B-Rennen','distance_km':10,'race_date':b_date.isoformat(),'goal_seconds':2650,'priority':'B'})
    assert b.status_code==201,b.text
    bweek=client.get(f"/api/week?start={b_ws.isoformat()}").json()
    assert any(w['workout_type']=='race' and w['details'].get('race_priority')=='B' for w in bweek['workouts'])

    # Complete a current planned workout with a real run, then account those
    # kilometers to a shoe through the new completed-workout action.
    shoe=client.post('/api/shoes',json={'brand':'ASICS','model':'Synthetic','nickname':'E2E','start_km':0}).json()['id']
    week=client.get('/api/week').json();workout=next(w for w in week['workouts'] if w['status']=='planned')
    inserted=client.post('/api/runs',json={'started_at':f"{workout['scheduled_date']}T07:30:00+02:00",'distance_km':workout['distance_km'],'duration_s':3300,'source':'manual'})
    assert inserted.status_code==200,inserted.text
    assigned=client.patch(f"/api/v2/workouts/{workout['id']}/shoe",json={'shoe_id':shoe})
    assert assigned.status_code==200,assigned.text
    shoe_row=next(s for s in client.get('/api/shoes').json() if s['id']==shoe)
    assert shoe_row['run_count']==1 and shoe_row['total_km']>=float(workout['distance_km'])-.05

    # API health exposes the release version through the active compatibility stack.
    assert client.get('/api/health').json()=={'ok':True,'version':main_v020.APP_VERSION}
