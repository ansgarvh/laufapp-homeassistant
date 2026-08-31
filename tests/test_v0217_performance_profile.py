from datetime import date, timedelta


def _seed_runs(c, weeks=8, weekly_km=56.0, runs_per_week=4):
    today=date.today(); current=today-timedelta(days=today.weekday())
    per=weekly_km/runs_per_week
    for wi in range(weeks,0,-1):
        ws=current-timedelta(days=7*wi)
        for ri in range(runs_per_week):
            day=ws+timedelta(days=min(ri*2,6))
            c.post('/api/runs',json={'started_at':day.isoformat()+'T08:00:00+02:00','distance_km':per,'duration_s':per*330,'avg_hr':138,'notes':'','source':'manual'})


def test_profile_is_structured_and_self_explaining(setup_client):
    c=setup_client;_seed_runs(c)
    p=c.get('/api/dashboard').json()['profile']
    assert p['profile_version']==2
    assert 'physiologisches Maximum' in p['scale_note']
    assert 'evidenzinformierte Heuristiken' in p['method_note']
    assert [m['label'] for m in p['metrics']]==['Ausdauerbasis','Speed-Ausdauer','Schwellen-Ausdauer','Marathon-Readiness','Trainingskontinuität']
    for m in p['metrics']:
        assert {'key','label','score','description','summary','components'} <= set(m)
        assert m['score'] is None or 0 <= m['score'] <= 100


def test_aerobic_base_uses_completed_weeks_not_partial_current_week(setup_client):
    c=setup_client;_seed_runs(c,weekly_km=55.0)
    p=c.get('/api/dashboard').json()['profile']
    aerobic=next(m for m in p['metrics'] if m['key']=='aerobic_base')
    assert aerobic['score'] >= 95
    assert '55.0 km' in aerobic['summary']


def test_training_continuity_uses_frequency_and_plan_completion(setup_client):
    c=setup_client;_seed_runs(c,weekly_km=48.0,runs_per_week=4)
    p=c.get('/api/dashboard').json()['profile']
    continuity=next(m for m in p['metrics'] if m['key']=='training_continuity')
    labels={x['label'] for x in continuity['components']}
    assert {'Aktive Wochen','Laufhäufigkeit','Planerfüllung'} <= labels
    assert 'aktive Wochen' in continuity['summary']


def test_readiness_label_tracks_active_race_distance(client):
    future=(date.today()+timedelta(days=90)).isoformat()
    r=client.post('/api/setup',json={'race_name':'Test HM','distance_km':21.0975,'race_date':future,'goal_seconds':6000,'training_days':[1,3,4,6]})
    assert r.status_code==200
    p=client.get('/api/dashboard').json()['profile']
    readiness=next(m for m in p['metrics'] if m['key']=='race_readiness')
    assert readiness['label']=='Halbmarathon-Readiness'


def test_legacy_profile_keys_remain_for_compatibility(setup_client):
    p=setup_client.get('/api/dashboard').json()['profile']
    for key in ['Grundlagenausdauer','Schwelle','Speed','Marathon-Ausdauer','Trainingskonstanz']:
        assert key in p


def test_frontend_explains_profile_and_health_context():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    js=(root/'laufapp/app/static/app.js').read_text()
    css=(root/'laufapp/app/static/assets/v0217.css').read_text()
    assert 'Was bedeutet 0–100?' in js
    assert 'profile-explainer' in js and 'profile-health' in js
    assert 'Nicht direkt in den Score eingerechnet.' in js
    assert 'Ausdauerbasis' in js and 'Schwellen-Ausdauer' in js and 'Speed-Ausdauer' in js
    assert '.profile-explainer' in css and '.profile-metric' in css
