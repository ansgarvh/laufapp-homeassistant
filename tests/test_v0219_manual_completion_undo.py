from pathlib import Path


def _first_workout(client):
    week=client.get('/api/week').json()
    assert week['workouts']
    return week['workouts'][0]


def test_manual_completion_can_be_reverted_to_planned(setup_client):
    client=setup_client
    w=_first_workout(client)
    r=client.post(f"/api/workouts/{w['id']}/status",json={'status':'completed'})
    assert r.status_code==200, r.text
    assert r.json()=={'ok':True}
    row=next(x for x in client.get('/api/week').json()['workouts'] if x['id']==w['id'])
    assert row['status']=='completed' and row['linked_run_id'] is None
    r=client.post(f"/api/workouts/{w['id']}/status",json={'status':'planned'})
    assert r.status_code==200, r.text
    assert r.json()=={'ok':True}
    row=next(x for x in client.get('/api/week').json()['workouts'] if x['id']==w['id'])
    assert row['status']=='planned' and row['linked_run_id'] is None
    assert row['manual_override']==1 and row['modified_by']=='user'


def test_linked_completion_cannot_be_reverted_or_skipped(setup_client):
    client=setup_client
    w=_first_workout(client)
    r=client.post('/api/runs',json={'started_at':f"{w['scheduled_date']}T08:00:00+00:00",'distance_km':w['distance_km'],'duration_s':max(1800,w['distance_km']*330),'source':'manual'})
    assert r.status_code==200, r.text
    linked=next(x for x in client.get('/api/week').json()['workouts'] if x['id']==w['id'])
    assert linked['status']=='completed' and linked['linked_run_id'] is not None
    r=client.post(f"/api/workouts/{w['id']}/status",json={'status':'completed'})
    assert r.status_code==200 and r.json()=={'ok':True}
    for status in ('planned','skipped'):
        r=client.post(f"/api/workouts/{w['id']}/status",json={'status':status})
        assert r.status_code==409, r.text
    linked=next(x for x in client.get('/api/week').json()['workouts'] if x['id']==w['id'])
    assert linked['status']=='completed' and linked['linked_run_id'] is not None


def test_ui_offers_undo_only_for_manual_unlinked_completion():
    js=(Path(__file__).resolve().parents[1]/'laufapp/app/static/app.js').read_text()
    assert 'Absolvierung zurücknehmen' in js
    assert "setWorkoutStatus(id,'planned')" in js
    assert 'Diese Absolvierung stammt aus einem verknüpften Lauf' in js
    assert "w.linked_run_id!==null&&w.linked_run_id!==undefined" in js
