from datetime import date, timedelta, datetime, timezone
import zipfile

def dtstr(d,h=8):
    return f"{d.isoformat()} {h:02d}:00:00 +0200"

def make_export(path):
    today=date.today(); recent=today-timedelta(days=30); old=date(today.year-3,today.month,min(today.day,20)); night=today-timedelta(days=3)
    xml=f'''<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
  <Record type="HKQuantityTypeIdentifierRestingHeartRate" sourceName="Watch" unit="count/min" creationDate="{dtstr(recent)}" startDate="{dtstr(recent)}" endDate="{dtstr(recent)}" value="48" uuid="rhr-1"/>
  <Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN" sourceName="Watch" unit="ms" creationDate="{dtstr(recent)}" startDate="{dtstr(recent)}" endDate="{dtstr(recent)}" value="55" uuid="hrv-1"/>
  <Record type="HKQuantityTypeIdentifierBodyMass" sourceName="Health" unit="kg" creationDate="{dtstr(recent)}" startDate="{dtstr(recent)}" endDate="{dtstr(recent)}" value="87.2" uuid="mass-1"/>
  <Record type="HKCategoryTypeIdentifierSleepAnalysis" value="HKCategoryValueSleepAnalysisAsleepCore" startDate="{night.isoformat()} 22:00:00 +0200" endDate="{(night+timedelta(days=1)).isoformat()} 02:00:00 +0200"/>
  <Record type="HKCategoryTypeIdentifierSleepAnalysis" value="HKCategoryValueSleepAnalysisAsleepREM" startDate="{(night+timedelta(days=1)).isoformat()} 01:30:00 +0200" endDate="{(night+timedelta(days=1)).isoformat()} 06:00:00 +0200"/>
  <Record type="HKQuantityTypeIdentifierRestingHeartRate" unit="count/min" startDate="{dtstr(old)}" endDate="{dtstr(old)}" value="60" uuid="old-rhr"/>
  <Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="60" durationUnit="min" totalDistance="12.0" totalDistanceUnit="km" startDate="{dtstr(recent)}" endDate="{dtstr(recent,9)}" uuid="run-1"><WorkoutStatistics type="HKQuantityTypeIdentifierHeartRate" average="145" unit="count/min"/></Workout>
  <Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="50" durationUnit="min" totalDistance="10.0" totalDistanceUnit="km" startDate="{dtstr(old)}" endDate="{dtstr(old,9)}" uuid="old-run"/>
</HealthData>'''
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('apple_health_export/export.xml',xml)

def test_health_24_month_filter_sleep_merge_and_dedupe(setup_client,tmp_path):
    c=setup_client;p=tmp_path/'export.zip';make_export(p)
    with p.open('rb') as f:r=c.post('/api/apple-health/import',files={'file':('export.zip',f,'application/zip')})
    assert r.status_code==200,r.text;data=r.json();assert data['runs_added']==1
    assert data['metrics_added']==4
    assert data['health_summary']['resting_hr']['latest']==48
    assert 8.0 <= data['health_summary']['sleep_hours']['latest'] <= 8.01
    with p.open('rb') as f:r2=c.post('/api/apple-health/import',files={'file':('export.zip',f,'application/zip')})
    assert r2.json()['runs_added']==0 and r2.json()['metrics_added']==0

def test_health_import_merges_matching_manual_screenshot_run(setup_client,tmp_path):
    c=setup_client; recent=date.today()-timedelta(days=30)
    manual=c.post('/api/runs',json={'started_at':recent.isoformat()+'T08:05:00+02:00','distance_km':12.0,'duration_s':3600,'rpe':4,'notes':'vom Screenshot','source':'screenshot'}).json()['id']
    p=tmp_path/'merge.zip';make_export(p)
    with p.open('rb') as f:r=c.post('/api/apple-health/import',files={'file':('merge.zip',f,'application/zip')})
    assert r.status_code==200 and r.json()['runs_merged']==1 and r.json()['runs_added']==0
    runs=c.get('/api/runs').json();match=next(x for x in runs if x['id']==manual)
    assert match['avg_hr']==145 and match['rpe']==4 and match['notes']=='vom Screenshot'
    assert len([x for x in runs if abs(x['distance_km']-12)<.01])==1
