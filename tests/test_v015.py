from datetime import date, timedelta
import zipfile


def test_nested_workout_statistics_diagnostics_and_reimport(setup_client,tmp_path):
    day=date.today()-timedelta(days=3)
    xml=f'''<HealthData>
<Record type="HKQuantityTypeIdentifierHeartRate" unit="count/min" startDate="{day} 08:01:00 +0200" endDate="{day} 08:01:05 +0200" value="140" uuid="nested-sample"/>
<Workout workoutActivityType="HKWorkoutActivityTypeRunning" startDate="{day} 08:00:00 +0200" endDate="{day} 09:00:00 +0200" uuid="nested-run">
<WorkoutStatistics type="HKQuantityTypeIdentifierDistanceWalkingRunning" sum="10" unit="km"/>
<WorkoutStatistics type="HKQuantityTypeIdentifierWorkoutDuration" sum="60" unit="min"/>
<WorkoutStatistics type="HKQuantityTypeIdentifierActiveEnergyBurned" sum="650" unit="kcal"/>
</Workout></HealthData>'''
    path=tmp_path/'nested.zip'
    with zipfile.ZipFile(path,'w') as z:z.writestr('apple_health_export/export.xml',xml)
    with path.open('rb') as f:first=setup_client.post('/api/apple-health/import',files={'file':('nested.zip',f,'application/zip')})
    assert first.status_code==200,first.text
    result=first.json();assert result['runs_added']==1 and result['run_samples_added']==1
    assert result['running_workouts_seen']==1 and result['running_workouts_rejected']==0 and result['classification']=='success'
    with path.open('rb') as f:second=setup_client.post('/api/apple-health/import',files={'file':('nested.zip',f,'application/zip')}).json()
    assert second['runs_added']==0 and second['runs_already_existing']==1 and second['classification']=='success'


def test_rejected_run_is_warning_with_reason(setup_client,tmp_path):
    day=date.today()-timedelta(days=2);path=tmp_path/'missing.xml'
    path.write_text(f'<HealthData><Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="30" durationUnit="min" startDate="{day} 08:00:00 +0200"/></HealthData>')
    with path.open('rb') as f:r=setup_client.post('/api/apple-health/import',files={'file':('missing.xml',f,'text/xml')}).json()
    assert r['classification']=='warning' and r['rejection_reasons']=={'missing_distance':1}


def test_progress_volume_counts_more_than_100_runs(setup_client):
    from db import db_conn
    today=date.today()
    with db_conn() as c:
        for i in range(130):
            d=today-timedelta(days=i%90)
            c.execute("INSERT INTO runs(external_id,started_at,distance_km,duration_s,source) VALUES(?,?,?,?, 'manual')",(f'volume-{i}',d.isoformat()+'T08:00:00+02:00',1,300))
    r=setup_client.get('/api/progress/volume?period=3m')
    assert r.status_code==200 and sum(x['run_count'] for x in r.json()['weeks'])==130 and r.json()['total_km']==130


def test_swap_rejects_completed_target_without_changes(setup_client):
    workouts=setup_client.get('/api/week').json()['workouts'];a,b=workouts[:2]
    setup_client.post(f"/api/workouts/{b['id']}/status",json={'status':'completed'})
    r=setup_client.post(f"/api/workouts/{a['id']}/move",json={'scheduled_date':b['scheduled_date']})
    assert r.status_code==400
    after=setup_client.get('/api/week').json()['workouts']
    assert next(x for x in after if x['id']==a['id'])['scheduled_date']==a['scheduled_date']
    assert next(x for x in after if x['id']==b['id'])['scheduled_date']==b['scheduled_date']
