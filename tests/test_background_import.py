import time, zipfile
from datetime import date, timedelta


def export_zip(path, malformed=False):
    d=date.today()-timedelta(days=10)
    tail='' if malformed else '</HealthData>'
    xml=f'''<?xml version="1.0"?><HealthData>
<Record type="HKQuantityTypeIdentifierRestingHeartRate" unit="count/min" startDate="{d} 07:00:00 +0200" endDate="{d} 07:00:00 +0200" value="47" uuid="bg-rhr"/>
<Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="60" durationUnit="min" totalDistance="12" totalDistanceUnit="km" startDate="{d} 08:00:00 +0200" endDate="{d} 09:00:00 +0200" uuid="bg-run"/>{tail}'''
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('apple_health_export/export.xml',xml)


def wait_job(c,jid,timeout=8):
    end=time.time()+timeout
    while time.time()<end:
        j=c.get(f'/api/apple-health/import-jobs/{jid}').json()
        if j['status'] in {'completed','failed'}:return j
        time.sleep(.05)
    raise AssertionError('background import did not finish')


def test_background_import_returns_after_upload_and_persists_status(setup_client,tmp_path):
    c=setup_client;p=tmp_path/'health.zip';export_zip(p)
    with p.open('rb') as f:r=c.post('/api/apple-health/import-jobs',files={'file':('health.zip',f,'application/zip')})
    assert r.status_code==202,r.text
    created=r.json();assert created['status']=='queued' and created['id']
    job=wait_job(c,created['id']);assert job['status']=='completed'
    assert job['progress']==1 and job['result']['runs_added']==1 and job['result']['metrics_added']==1
    assert c.get('/api/apple-health/import-jobs/latest').json()['id']==created['id']
    runs=c.get('/api/runs').json();assert any(x['external_id']=='bg-run' for x in runs)


def test_failed_background_import_rolls_back_health_data(setup_client,tmp_path):
    c=setup_client;p=tmp_path/'broken.zip';export_zip(p,malformed=True)
    before=len(c.get('/api/runs').json())
    with p.open('rb') as f:r=c.post('/api/apple-health/import-jobs',files={'file':('broken.zip',f,'application/zip')})
    job=wait_job(c,r.json()['id']);assert job['status']=='failed'
    assert len(c.get('/api/runs').json())==before


def test_interrupted_processing_job_is_resumed_on_app_manager_start(setup_client):
    """Simulate a container restart after upload but during server-side parsing."""
    import uuid
    import import_jobs
    from db import db_conn

    c=setup_client
    import_jobs.MANAGER.stop()
    job_uuid=str(uuid.uuid4())
    source=import_jobs.import_storage_path(job_uuid,'.zip')
    export_zip(source)
    job=import_jobs.create_import_job_with_uuid(job_uuid,'resume-health.zip',source,source.stat().st_size)
    with db_conn() as conn:
        conn.execute("UPDATE import_jobs SET status='processing',phase='Health-Daten & Workouts',progress=.4 WHERE id=?",(job['id'],))
    import_jobs.MANAGER.start()
    finished=wait_job(c,job['id'])
    assert finished['status']=='completed'
    assert finished['result']['runs_added']==1
    assert not source.exists()
