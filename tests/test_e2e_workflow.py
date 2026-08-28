from datetime import date, timedelta
from types import SimpleNamespace
import json, zipfile

def fake_response(payload):
    ann=SimpleNamespace(url='https://pubmed.ncbi.nlm.nih.gov/00000000/',title='Synthetic scientific source')
    msg=SimpleNamespace(type='message',content=[SimpleNamespace(annotations=[ann])])
    search=SimpleNamespace(type='web_search_call',content=[])
    return SimpleNamespace(output_text=json.dumps(payload),usage=SimpleNamespace(input_tokens=800,output_tokens=250),output=[search,msg])

def test_full_synthetic_user_workflow(client,tmp_path,monkeypatch):
    # 1. Onboarding and goal-time driven week.
    race_date=(date.today()+timedelta(days=80)).isoformat()
    setup=client.post('/api/setup',json={'race_name':'Synthetic Marathon','distance_km':42.195,'race_date':race_date,'goal_seconds':3*3600+25*60,'training_days':[1,3,4,6]})
    assert setup.status_code==200
    week=client.get('/api/week').json(); assert len(week['workouts'])==4

    # 2. Performance anchor -> race predictions.
    mark=client.post('/api/performance-marks',json={'distance_km':10,'duration_s':43*60,'mark_date':date.today().isoformat(),'source':'time_trial','label':'10k test'})
    assert mark.status_code==200 and len(mark.json()['predictions'])==4

    # 3. 24-month Apple Health export with relevant health + one run.
    recent=date.today()-timedelta(days=14)
    xml=f'''<HealthData>
    <Record type="HKQuantityTypeIdentifierRestingHeartRate" unit="count/min" startDate="{recent} 07:00:00 +0200" endDate="{recent} 07:00:00 +0200" value="49" uuid="e2e-rhr"/>
    <Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN" unit="ms" startDate="{recent} 07:00:00 +0200" endDate="{recent} 07:00:00 +0200" value="58" uuid="e2e-hrv"/>
    <Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="52" durationUnit="min" totalDistance="10.5" totalDistanceUnit="km" startDate="{recent} 08:00:00 +0200" endDate="{recent} 08:52:00 +0200" uuid="e2e-run"><WorkoutStatistics type="HKQuantityTypeIdentifierHeartRate" average="144" unit="count/min"/></Workout>
    </HealthData>'''
    z=tmp_path/'health.zip'
    with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as arc: arc.writestr('apple_health_export/export.xml',xml)
    with z.open('rb') as f: imported=client.post('/api/apple-health/import',files={'file':('health.zip',f,'application/zip')})
    assert imported.status_code==200 and imported.json()['runs_added']==1 and imported.json()['metrics_added']==2

    # 4. Shoe master data + post-run assignment/matching.
    sid=client.post('/api/shoes',json={'brand':'ASICS','model':'Superblast 2','nickname':'Daily','start_km':200}).json()['id']
    open_workout=next(x for x in client.get('/api/week').json()['workouts'] if x['status']=='planned')
    added=client.post('/api/runs',json={'started_at':open_workout['scheduled_date']+'T08:00:00+02:00','distance_km':open_workout['distance_km'],'duration_s':open_workout['distance_km']*330,'avg_hr':143,'elevation_m':110,'rpe':3,'shoe_id':sid,'notes':'synthetic e2e','source':'manual'})
    assert added.status_code==200 and added.json()['matched_workout_id']==open_workout['id']
    assert client.get('/api/shoes').json()[0]['total_km']>200

    # 5. Runna-inspired preferences regenerate only an open week when safe.
    saved=client.patch('/api/settings',json={'training_volume_profile':'gradual','training_difficulty':'comfortable','max_long_run_km':28,'max_long_run_share':.42,'monthly_ai_budget_eur':10})
    assert saved.status_code==200 and saved.json()['training_difficulty']=='comfortable'

    # 6. AI coach and science review are connected, but plan change stays confirmation-gated.
    import coach
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-test-key')
    current=next(x for x in client.get('/api/week').json()['workouts'] if x['status']=='planned')
    replies=iter([
        fake_response({'reply':'Die Woche ist insgesamt plausibel; ich schlage nur eine kleine Recovery-Anpassung vor.','suggestion':{'title':'Recovery feinjustieren','rationale':'Konservativer Schritt nach belastendem Training.','workout_id':current['id'],'changes':{'distance_km':max(3,current['distance_km']-1)}}}),
        fake_response({'review':'Die vier Einheiten sind plausibel verteilt. Belastungsspitzen bleiben getrennt; der Longrun liegt im gesetzten Guardrail.','suggestion':None})
    ])
    monkeypatch.setattr(coach,'request',lambda *a,**k:next(replies))
    chat=client.post('/api/coach/chat',json={'message':'Bewerte die kommende Trainingswoche.'}).json(); assert chat['suggestion_id']
    before=next(x for x in client.get('/api/week').json()['workouts'] if x['id']==current['id'])['distance_km']
    # Explicit reject: no hidden plan mutation.
    assert client.post(f"/api/suggestions/{chat['suggestion_id']}/reject").status_code==200
    after=next(x for x in client.get('/api/week').json()['workouts'] if x['id']==current['id'])['distance_km']; assert after==before
    review=client.post('/api/plan/review').json(); assert 'plausibel' in review['review_text'] and review['sources']

    # 7. Final dashboard is internally consistent and exposes no key.
    dash=client.get('/api/dashboard').json(); boot=client.get('/api/bootstrap').json(); usage=client.get('/api/ai-usage').json()
    assert dash['race']['name']=='Synthetic Marathon' and dash['week']['planned_km']>0
    assert boot['ai']['configured'] is True and 'openai_api_key' not in json.dumps(boot)
    assert usage['month_cost_eur']>=0
