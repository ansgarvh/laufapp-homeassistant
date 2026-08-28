import json
from types import SimpleNamespace

def response(payload, with_source=True):
    ann=SimpleNamespace(url='https://pubmed.ncbi.nlm.nih.gov/example',title='Peer reviewed source')
    content=SimpleNamespace(annotations=[ann] if with_source else [])
    out=[SimpleNamespace(type='web_search_call',content=[]),SimpleNamespace(type='message',content=[content])]
    return SimpleNamespace(output_text=json.dumps(payload),usage=SimpleNamespace(input_tokens=1000,output_tokens=300),output=out)

def enable_ai(monkeypatch): monkeypatch.setenv('OPENAI_API_KEY','test-key')

def test_chat_creates_confirmation_gated_suggestion(setup_client,monkeypatch):
    import coach
    enable_ai(monkeypatch)
    w=setup_client.get('/api/week').json()['workouts'][0]
    monkeypatch.setattr(coach,'request',lambda *a,**k:response({'reply':'Reduziere die lockere Einheit leicht.','suggestion':{'title':'Recovery-Anpassung','rationale':'Konservativ reduzieren.','workout_id':w['id'],'changes':{'distance_km':max(3,w['distance_km']-1)}}}))
    r=setup_client.post('/api/coach/chat',json={'message':'Passe die Woche an.'})
    assert r.status_code==200 and r.json()['suggestion_id']
    before=next(x for x in setup_client.get('/api/week').json()['workouts'] if x['id']==w['id'])['distance_km']
    assert before==w['distance_km'] # not auto-applied
    sid=r.json()['suggestion_id'];assert setup_client.post(f'/api/suggestions/{sid}/accept').status_code==200
    after=next(x for x in setup_client.get('/api/week').json()['workouts'] if x['id']==w['id'])['distance_km']
    assert after<before

def test_plan_review_uses_science_tool_and_is_cached(setup_client,monkeypatch):
    import coach
    enable_ai(monkeypatch);calls=[]
    def fake(*a,**k):calls.append(a[2] if len(a)>2 else k.get('tools'));return response({'review':'Plan ist konservativ strukturiert.','suggestion':None})
    monkeypatch.setattr(coach,'request',fake)
    r=setup_client.post('/api/plan/review');assert r.status_code==200 and 'konservativ' in r.json()['review_text']
    assert calls and calls[0]==[{'type':'web_search'}]
    r2=setup_client.post('/api/plan/review');assert r2.status_code==200 and len(calls)==1

def test_screenshot_extract_then_user_must_save(setup_client,monkeypatch):
    import coach
    enable_ai(monkeypatch)
    monkeypatch.setattr(coach,'request',lambda *a,**k:response({'distance_km':10.1,'duration_seconds':2700,'avg_hr':151,'elevation_m':75,'calories':700,'started_at':None,'confidence':.96,'notes':'sichtbar'},False))
    before=len(setup_client.get('/api/runs').json())
    r=setup_client.post('/api/coach/extract-run',files={'file':('shot.png',b'fake-image','image/png')})
    assert r.status_code==200 and r.json()['distance_km']==10.1
    assert len(setup_client.get('/api/runs').json())==before # extraction never stores without confirmation
