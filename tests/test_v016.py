import time
from datetime import date, timedelta
from pathlib import Path

from db import db_conn


def xml_export(path: Path, run_id='replace-run', distance=10, malformed=False):
    recent=date.today()-timedelta(days=5); old=date.today()-timedelta(days=800)
    close='' if malformed else '</HealthData>'
    path.write_text(f'''<HealthData>
<Record type="HKQuantityTypeIdentifierRestingHeartRate" unit="count/min" startDate="{recent} 07:00:00 +0200" endDate="{recent} 07:00:00 +0200" value="48" uuid="metric-new"/>
<Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="50" durationUnit="min" totalDistance="{distance}" totalDistanceUnit="km" startDate="{recent} 08:00:00 +0200" endDate="{recent} 08:50:00 +0200" uuid="{run_id}"/>
<Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="40" durationUnit="min" totalDistance="8" totalDistanceUnit="km" startDate="{old} 08:00:00 +0200" endDate="{old} 08:40:00 +0200" uuid="old-run"/>{close}''')


def wait_job(c,jid):
    for _ in range(160):
        job=c.get(f'/api/apple-health/import-jobs/{jid}').json()
        if job['status'] in {'completed','failed'}: return job
        time.sleep(.05)
    raise AssertionError('job timeout')


def test_health_categories_existing_metrics_and_recovery(setup_client,tmp_path):
    p=tmp_path/'export.xml';xml_export(p)
    with p.open('rb') as f:first=setup_client.post('/api/apple-health/import',files={'file':('export.xml',f,'text/xml')}).json()
    assert first['running_workouts_seen_total']==2
    assert first['running_workouts_in_period']==1 and first['running_workouts_outside_period']==1
    assert first['running_workouts_invalid']==0 and first['runs_added']==1
    with p.open('rb') as f:second=setup_client.post('/api/apple-health/import',files={'file':('export.xml',f,'text/xml')}).json()
    assert second['metric_records_seen']['resting_hr']==1
    assert second['metric_records_added']['resting_hr']==0
    assert second['runs_already_existing']==1
    assert setup_client.get('/api/dashboard').json()['health']['resting_hr']['latest']==48


def test_invalid_running_reasons_are_separate(setup_client,tmp_path):
    d=date.today()-timedelta(days=2);p=tmp_path/'invalid.xml'
    p.write_text(f'''<HealthData>
<Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="30" durationUnit="min" startDate="{d} 08:00:00 +0200"/>
<Workout workoutActivityType="HKWorkoutActivityTypeRunning" totalDistance="5" totalDistanceUnit="km" startDate="{d} 09:00:00 +0200"/>
</HealthData>''')
    with p.open('rb') as f:r=setup_client.post('/api/apple-health/import',files={'file':('invalid.xml',f,'text/xml')}).json()
    assert r['running_workouts_invalid']==2 and r['running_workouts_outside_period']==0
    assert r['invalid_rejection_reasons']=={'missing_distance':1,'missing_duration':1}


def test_replacement_is_transactional_scoped_and_preserves_metadata(setup_client,tmp_path):
    p=tmp_path/'first.xml';xml_export(p)
    with p.open('rb') as f:setup_client.post('/api/apple-health/import',files={'file':('first.xml',f,'text/xml')})
    with db_conn() as c:
        shoe=c.execute("INSERT INTO shoes(model) VALUES('Keep')").lastrowid
        c.execute("UPDATE runs SET shoe_id=?,rpe=7,notes='keep' WHERE external_id='replace-run'",(shoe,))
        c.execute("INSERT INTO settings(key,value) VALUES('keep-setting','true')")
        c.execute("INSERT INTO races(name,distance_km,race_date,goal_seconds) VALUES('Keep',10,?,3000)",((date.today()+timedelta(days=30)).isoformat(),))
    replacement=tmp_path/'replacement.xml';xml_export(replacement,distance=11)
    with replacement.open('rb') as f:created=setup_client.post('/api/apple-health/import-jobs?replace_existing=true',files={'file':('replacement.xml',f,'text/xml')}).json()
    job=wait_job(setup_client,created['id']);assert job['status']=='completed' and job['result']['import_mode']=='replace'
    with db_conn() as c:
        run=c.execute("SELECT * FROM runs WHERE external_id='replace-run'").fetchone()
        assert run['distance_km']==11 and run['shoe_id']==shoe and run['rpe']==7 and run['notes']=='keep'
        assert c.execute("SELECT COUNT(*) FROM races WHERE name='Keep'").fetchone()[0]==1
        assert c.execute("SELECT COUNT(*) FROM settings WHERE key='keep-setting'").fetchone()[0]==1
    broken=tmp_path/'broken.xml';xml_export(broken,malformed=True)
    with broken.open('rb') as f:created=setup_client.post('/api/apple-health/import-jobs?replace_existing=true',files={'file':('broken.xml',f,'text/xml')}).json()
    assert wait_job(setup_client,created['id'])['status']=='failed'
    with db_conn() as c:assert c.execute("SELECT distance_km FROM runs WHERE external_id='replace-run'").fetchone()[0]==11


def test_calendar_year_progress_excludes_cross_boundary_runs(setup_client):
    today=date.today(); previous=today.year-1
    with db_conn() as c:
        for external,day,km in [('dec',date(previous,12,31),7),('jan',date(today.year,1,1),11)]:
            c.execute("INSERT INTO runs(external_id,started_at,distance_km,duration_s) VALUES(?,?,?,3600)",(external,day.isoformat()+'T08:00:00+00:00',km))
    current=setup_client.get('/api/progress/volume?period=this_year').json()
    last=setup_client.get('/api/progress/volume?period=last_year').json()
    assert current['cutoff_date']==f'{today.year}-01-01' and current['total_km']==11
    assert last['through_date']==f'{previous}-12-31' and last['total_km']==7


def test_v016_frontend_interactions_are_shared_and_accessible():
    js=Path('laufapp/app/static/app.js').read_text()
    assert "uploadHealthFile(e.target.files?.[0]" in js and "uploadHealthFile(files[0])" in js
    assert "data-drop-date=\"${esc(w.scheduled_date)}\"" in js
    assert "['this_year','Dieses Jahr']" in js and 'week-tooltip' in js
    assert 'replace_existing=${replace}' in js
