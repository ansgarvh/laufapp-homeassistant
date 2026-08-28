from datetime import date, timedelta
import zipfile


def test_detailed_running_samples_and_gpx_are_linked(setup_client,tmp_path):
    c=setup_client;d=date.today()-timedelta(days=5)
    xml=f'''<HealthData>
<Record type="HKQuantityTypeIdentifierHeartRate" unit="count/min" startDate="{d} 08:01:00 +0200" endDate="{d} 08:01:05 +0200" value="142" uuid="hr-142"/>
<Record type="HKQuantityTypeIdentifierRunningPower" unit="W" startDate="{d} 08:01:00 +0200" endDate="{d} 08:01:05 +0200" value="330" uuid="power-330"/>
<Record type="HKQuantityTypeIdentifierRunningSpeed" unit="m/s" startDate="{d} 08:01:00 +0200" endDate="{d} 08:01:05 +0200" value="3.6" uuid="speed-36"/>
<Record type="HKQuantityTypeIdentifierRunningStrideLength" unit="m" startDate="{d} 08:01:00 +0200" endDate="{d} 08:01:05 +0200" value="1.18" uuid="stride-118"/>
<Record type="HKQuantityTypeIdentifierRunningVerticalOscillation" unit="cm" startDate="{d} 08:01:00 +0200" endDate="{d} 08:01:05 +0200" value="8.4" uuid="vo-84"/>
<Record type="HKQuantityTypeIdentifierRunningGroundContactTime" unit="ms" startDate="{d} 08:01:00 +0200" endDate="{d} 08:01:05 +0200" value="242" uuid="gct-242"/>
<Record type="HKQuantityTypeIdentifierStepCount" unit="count" startDate="{d} 08:01:00 +0200" endDate="{d} 08:02:00 +0200" value="168" uuid="steps-168"/>
<Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="60" durationUnit="min" totalDistance="12" totalDistanceUnit="km" startDate="{d} 08:00:00 +0200" endDate="{d} 09:00:00 +0200" uuid="detail-run"><WorkoutStatistics type="HKQuantityTypeIdentifierHeartRate" average="145" unit="count/min"/></Workout>
</HealthData>'''
    gpx=f'''<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>
<trkpt lat="50.0000" lon="6.0000"><ele>100</ele><time>{d}T06:00:10Z</time></trkpt>
<trkpt lat="50.0001" lon="6.0001"><ele>102</ele><time>{d}T06:00:20Z</time></trkpt>
<trkpt lat="50.0002" lon="6.0002"><ele>101</ele><time>{d}T06:00:30Z</time></trkpt>
</trkseg></trk></gpx>'''
    p=tmp_path/'detailed.zip'
    with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('apple_health_export/export.xml',xml);z.writestr('apple_health_export/workout-routes/route_1.gpx',gpx)
    with p.open('rb') as f:r=c.post('/api/apple-health/import',files={'file':('detailed.zip',f,'application/zip')})
    assert r.status_code==200,r.text;data=r.json();assert data['run_samples_added']==7 and data['gps_points_added']==3
    run=next(x for x in c.get('/api/runs').json() if x['external_id']=='detail-run')
    details=c.get(f"/api/runs/{run['id']}/details").json();types={x['metric_type']:x for x in details['sample_summary']}
    assert {'heart_rate','running_power','running_speed','stride_length','vertical_oscillation','ground_contact_time','cadence'} <= set(types)
    assert round(types['cadence']['average'])==168
    assert details['gps_points']==3
