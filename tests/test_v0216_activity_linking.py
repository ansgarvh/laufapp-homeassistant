def _add_run(c, workout, ratio):
    return c.post('/api/runs',json={'started_at':workout['scheduled_date']+'T08:00:00+02:00','distance_km':float(workout['distance_km'])*ratio,'duration_s':3600,'notes':'','source':'manual'})

def test_auto_match_rejects_more_than_ten_percent_short(setup_client):
    c=setup_client;w=c.get('/api/week').json()['workouts'][0];r=_add_run(c,w,0.899);assert r.status_code==200 and r.json()['matched_workout_id'] is None;ww=next(x for x in c.get('/api/week').json()['workouts'] if x['id']==w['id']);assert ww['status']=='planned' and ww['linked_run_id'] is None

def test_auto_match_accepts_exactly_ninety_percent(setup_client):
    c=setup_client;w=c.get('/api/week').json()['workouts'][0];r=_add_run(c,w,0.90);assert r.status_code==200 and r.json()['matched_workout_id']==w['id']

def test_auto_match_accepts_overfulfilment(setup_client):
    c=setup_client;w=c.get('/api/week').json()['workouts'][0];r=_add_run(c,w,1.40);assert r.status_code==200 and r.json()['matched_workout_id']==w['id']

def test_short_run_can_be_manually_linked_same_day(setup_client):
    c=setup_client;w=c.get('/api/week').json()['workouts'][0];r=_add_run(c,w,0.60);rid=r.json()['id'];info=c.get(f'/api/runs/{rid}/link-candidates');assert info.status_code==200 and any(x['id']==w['id'] for x in info.json()['candidates']);linked=c.post(f'/api/runs/{rid}/link-workout/{w["id"]}');assert linked.status_code==200 and linked.json()['workout']['status']=='completed';info2=c.get(f'/api/runs/{rid}/link-candidates').json();assert info2['linked_workout']['id']==w['id'] and info2['candidates']==[]

def test_manual_link_rejects_different_day(setup_client):
    c=setup_client;workouts=c.get('/api/week').json()['workouts'];w1,w2=workouts[0],workouts[1];r=_add_run(c,w1,0.50);rid=r.json()['id'];out=c.post(f'/api/runs/{rid}/link-workout/{w2["id"]}');assert out.status_code==409

def test_ui_exposes_manual_link_action():
    from pathlib import Path
    js=(Path(__file__).resolve().parents[1]/'laufapp/app/static/app.js').read_text();assert 'Aktivität verknüpfen' in js;assert 'api/runs/${id}/link-candidates' in js;assert 'api/runs/${run.id}/link-workout/${b.dataset.linkWorkout}' in js;assert 'mindestens 90 %' in js
