from datetime import date, timedelta

def test_setup_generates_four_days_and_rpe(setup_client):
    c=setup_client; w=c.get('/api/week').json()
    assert len(w['workouts'])==4
    assert sorted(date.fromisoformat(x['scheduled_date']).weekday() for x in w['workouts'])==[1,3,4,6]
    assert all(x['details'].get('rpe_target') for x in w['workouts'])
    assert w['guardrails']['long_run_share'] <= .45 + .02

def test_prediction_and_adopt(setup_client):
    c=setup_client
    mark=date.today().isoformat()
    assert c.post('/api/performance-marks',json={'distance_km':21.0975,'duration_s':97*60,'mark_date':mark,'source':'race','label':'HM'}).status_code==200
    p=c.get('/api/predictions').json()['predictions']
    assert {round(x['distance_km'],1) for x in p} >= {5.0,10.0,21.1,42.2}
    race=c.get('/api/races').json()[0]
    r=c.post(f"/api/races/{race['id']}/adopt-prediction")
    assert r.status_code==200 and r.json()['goal_seconds']>0

def test_shoe_mileage_and_run_match(setup_client):
    c=setup_client
    sid=c.post('/api/shoes',json={'brand':'ASICS','model':'Superblast 2','nickname':'Daily','start_km':12.5}).json()['id']
    w=c.get('/api/week').json()['workouts'][0]
    r=c.post('/api/runs',json={'started_at':w['scheduled_date']+'T08:00:00+02:00','distance_km':w['distance_km'],'duration_s':3600,'avg_hr':142,'elevation_m':80,'rpe':3,'shoe_id':sid,'notes':'gut','source':'manual'})
    assert r.status_code==200 and r.json()['matched_workout_id']==w['id']
    shoe=c.get('/api/shoes').json()[0]
    assert abs(shoe['total_km']-(12.5+w['distance_km']))<.11 and shoe['run_count']==1
    ww=c.get('/api/week').json()['workouts']
    assert next(x for x in ww if x['id']==w['id'])['status']=='completed'

def test_move_swap_and_adjacent_warning(setup_client):
    c=setup_client; workouts=c.get('/api/week').json()['workouts']
    first,second=workouts[0],workouts[1]
    coll=c.post(f"/api/workouts/{first['id']}/move",json={'scheduled_date':second['scheduled_date']})
    assert coll.status_code==200 and coll.json()['operation']=='swap'
    swapped=c.get('/api/week').json()['workouts']
    assert next(x for x in swapped if x['id']==first['id'])['scheduled_date']==second['scheduled_date']
    assert next(x for x in swapped if x['id']==second['id'])['scheduled_date']==first['scheduled_date']
    workouts=swapped
    # move quality next to long run when possible -> warning is allowed/expected for hard pair
    quality=next(x for x in workouts if x['workout_type']=='quality'); long=next(x for x in workouts if x['workout_type']=='long')
    proposed=(date.fromisoformat(long['scheduled_date'])-timedelta(days=1)).isoformat()
    # if occupied, move long next to quality instead
    if any(x['scheduled_date']==proposed and x['id']!=quality['id'] for x in workouts):
        proposed=(date.fromisoformat(quality['scheduled_date'])+timedelta(days=1)).isoformat(); target=long
    else: target=quality
    rr=c.post(f"/api/workouts/{target['id']}/move",json={'scheduled_date':proposed})
    assert rr.status_code in (200,400)
    if rr.status_code==200: assert isinstance(rr.json()['warnings'],list)

def test_preferences_replan_and_cap(setup_client):
    c=setup_client
    r=c.patch('/api/settings',json={'training_volume_profile':'gradual','training_difficulty':'comfortable','baseline_weekly_km':68,'max_long_run_km':24,'max_long_run_share':.40})
    assert r.status_code==200
    assert c.get('/api/week').json()['plan_stale'] is True
    assert c.post('/api/plan/refresh?weeks=1').status_code==200
    w=c.get('/api/week').json()
    long=max(x['distance_km'] for x in w['workouts'] if x['workout_type']=='long')
    assert long<=24.0
    assert w['guardrails']['long_run_share']<=.415

def test_ai_without_key_fails_cleanly(setup_client):
    r=setup_client.post('/api/coach/chat',json={'message':'Wie ist meine Form?'})
    assert r.status_code==400 and 'API' in r.json()['detail']

def test_cross_week_move_keeps_receiving_week_complete(setup_client):
    c=setup_client
    current=c.get('/api/week').json(); moved=current['workouts'][0]
    target=(date.fromisoformat(current['week_end'])+timedelta(days=2)).isoformat()  # Tuesday next week
    r=c.post(f"/api/workouts/{moved['id']}/move",json={'scheduled_date':target})
    assert r.status_code==200,r.text
    next_start=(date.fromisoformat(current['week_start'])+timedelta(days=7)).isoformat()
    nxt=c.get('/api/week?start='+next_start).json()
    native=[x for x in nxt['workouts'] if x['origin_week_start']==next_start]
    assert len(native)==4
    assert any(x['id']==moved['id'] for x in nxt['workouts'])

def test_imported_or_manual_run_can_be_enriched_with_shoe_and_rpe(setup_client):
    c=setup_client
    sid=c.post('/api/shoes',json={'brand':'ASICS','model':'Magic Speed 5','nickname':'Tempo','start_km':0}).json()['id']
    rid=c.post('/api/runs',json={'started_at':date.today().isoformat()+'T09:00:00+02:00','distance_km':9.5,'duration_s':2700,'notes':'','source':'manual'}).json()['id']
    r=c.patch(f'/api/runs/{rid}',json={'shoe_id':sid,'rpe':7,'notes':'kontrolliert'}); assert r.status_code==200
    assert r.json()['shoe_model']=='Magic Speed 5' and r.json()['rpe']==7 and r.json()['notes']=='kontrolliert'

def test_prepare_repository_transfer_endpoint(setup_client):
    r=setup_client.post('/api/system/prepare-repository-transfer')
    assert r.status_code==200 and r.json()['transfer']['size_bytes']>0
