from __future__ import annotations
import math
from datetime import datetime
from typing import Any
RUN_SAMPLE_TYPES={"distance","heart_rate","running_speed","running_power","stride_length","vertical_oscillation","ground_contact_time","cadence"}
HEALTH_METRIC_TYPES={"resting_hr","hrv_sdnn","body_mass","vo2max","sleep_hours"}
MAX_WORKOUTS_PER_REQUEST=4
MAX_SAMPLES_PER_WORKOUT=120000
MAX_ROUTE_POINTS_PER_WORKOUT=30000
MAX_HEALTH_METRICS_PER_REQUEST=20000

def _finite(value:Any,minimum=None,maximum=None):
    number=float(value)
    if not math.isfinite(number): raise ValueError("Nicht-endlicher Zahlenwert im HealthKit-Payload.")
    if minimum is not None and number<minimum: raise ValueError("HealthKit-Zahlenwert liegt unter dem erlaubten Bereich.")
    if maximum is not None and number>maximum: raise ValueError("HealthKit-Zahlenwert liegt über dem erlaubten Bereich.")
    return number

def _iso(value:Any):
    text=str(value or "").strip()
    if not text: raise ValueError("HealthKit-Zeitstempel fehlt.")
    try: datetime.fromisoformat(text.replace("Z","+00:00"))
    except ValueError as exc: raise ValueError("Ungültiger HealthKit-Zeitstempel.") from exc
    return text

def _id(value:Any):
    text=str(value or "").strip()
    if not text or len(text)>160: raise ValueError("Ungültige HealthKit-ID.")
    return text

def _optional_number(value,minimum=None,maximum=None):
    return None if value is None else _finite(value,minimum,maximum)

def _insert_or_enrich_run(c,workout,training):
    external_id=_id(workout.get("id")); started_at=_iso(workout.get("start_at")); ended_at=_iso(workout.get("end_at"))
    distance_km=_finite(workout.get("distance_km"),0.01,500); duration_s=_finite(workout.get("duration_s"),1,172800)
    avg_hr=_optional_number(workout.get("avg_hr"),20,260); elevation_m=_optional_number(workout.get("elevation_m"),-10000,100000); calories=_optional_number(workout.get("calories"),0,100000)
    existing=c.execute("SELECT * FROM runs WHERE external_id=?",(external_id,)).fetchone()
    if existing:
        c.execute("UPDATE runs SET ended_at=COALESCE(ended_at,?),avg_hr=COALESCE(avg_hr,?),elevation_m=COALESCE(elevation_m,?),calories=COALESCE(calories,?),source=CASE WHEN source='manual' THEN 'apple_health_live' ELSE source END WHERE id=?",(ended_at,avg_hr,elevation_m,calories,existing["id"]))
        return int(existing["id"]),False
    cur=c.execute("INSERT INTO runs(external_id,started_at,ended_at,distance_km,duration_s,avg_hr,elevation_m,calories,source) VALUES(?,?,?,?,?,?,?,?,?)",(external_id,started_at,ended_at,distance_km,duration_s,avg_hr,elevation_m,calories,"apple_health_live"))
    run_id=int(cur.lastrowid); training.auto_match_run(c,run_id); return run_id,True

def _insert_samples(c,run_id,samples):
    if len(samples)>MAX_SAMPLES_PER_WORKOUT: raise ValueError("Zu viele HealthKit-Messpunkte in einem Workout.")
    inserted=0
    for s in samples:
        t=str(s.get("type") or "")
        if t not in RUN_SAMPLE_TYPES: continue
        cur=c.execute("INSERT OR IGNORE INTO run_samples(external_id,run_id,metric_type,sampled_at,value,unit,source) VALUES(?,?,?,?,?,?,?)",(_id(s.get("id")),run_id,t,_iso(s.get("at")),_finite(s.get("value"),-1e6,1e6),str(s.get("unit") or "")[:40],"apple_health_live"))
        inserted+=int(bool(cur.rowcount))
    return inserted

def _insert_route(c,run_id,points):
    if len(points)>MAX_ROUTE_POINTS_PER_WORKOUT: raise ValueError("Zu viele GPS-Punkte in einem HealthKit-Workout.")
    inserted=0
    for sequence,p in enumerate(points):
        cur=c.execute("INSERT OR IGNORE INTO gps_points(run_id,sampled_at,latitude,longitude,elevation_m,sequence,source) VALUES(?,?,?,?,?,?,?)",(run_id,_iso(p.get("at")),_finite(p.get("lat"),-90,90),_finite(p.get("lon"),-180,180),_optional_number(p.get("elevation_m"),-1000,12000),sequence,"apple_health"))
        inserted+=int(bool(cur.rowcount))
    return inserted

def _insert_health_metrics(c,metrics):
    if len(metrics)>MAX_HEALTH_METRICS_PER_REQUEST: raise ValueError("Zu viele allgemeine HealthKit-Messwerte in einer Anfrage.")
    inserted=0
    for m in metrics:
        t=str(m.get("type") or "")
        if t not in HEALTH_METRIC_TYPES: continue
        end=m.get("end_at")
        cur=c.execute("INSERT OR IGNORE INTO health_metrics(external_id,metric_type,start_at,end_at,value,unit,source) VALUES(?,?,?,?,?,?,?)",(_id(m.get("id")),t,_iso(m.get("start_at")),_iso(end) if end else None,_finite(m.get("value"),-1e6,1e6),str(m.get("unit") or "")[:40],"apple_health_live"))
        inserted+=int(bool(cur.rowcount))
    return inserted

def ingest_healthkit_payload(c,payload,training,performance_sync=None):
    if not isinstance(payload,dict) or payload.get("schema_version")!=1: raise ValueError("Nicht unterstützte HealthKit-Payload-Version.")
    workouts=payload.get("workouts") or []; metrics=payload.get("metrics") or []
    if not isinstance(workouts,list) or not isinstance(metrics,list): raise ValueError("Ungültiges HealthKit-Payload-Format.")
    if len(workouts)>MAX_WORKOUTS_PER_REQUEST: raise ValueError("Zu viele Workouts in einer HealthKit-Anfrage.")
    stats={"workouts_received":len(workouts),"workouts_added":0,"workouts_existing":0,"samples_added":0,"gps_points_added":0,"health_metrics_added":0}
    for w in workouts:
        if not isinstance(w,dict): raise ValueError("Ungültiger Workout-Eintrag.")
        if str(w.get("activity_type") or "").lower()!="running": continue
        run_id,added=_insert_or_enrich_run(c,w,training); stats["workouts_added" if added else "workouts_existing"]+=1
        samples=w.get("samples") or []; route=w.get("route") or []
        if not isinstance(samples,list) or not isinstance(route,list): raise ValueError("Ungültige Workout-Zeitreihen.")
        stats["samples_added"]+=_insert_samples(c,run_id,samples); stats["gps_points_added"]+=_insert_route(c,run_id,route)
    stats["health_metrics_added"]=_insert_health_metrics(c,metrics)
    stats["performance_marks_detected"]=int(performance_sync(c,training,24)) if performance_sync is not None and workouts else 0
    return stats
