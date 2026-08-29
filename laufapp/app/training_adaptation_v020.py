from __future__ import annotations

import json
import math
import statistics
from datetime import date, datetime, timedelta, timezone
from typing import Any

import training as base
from db import get_setting, set_setting
from training_models_v020 import ReadinessLevel, RecoveryState


def feedback_key(run_id:int)->str:return f"workout_feedback:{int(run_id)}"


def _json_setting_rows(c,prefix:str)->list[dict[str,Any]]:
    out=[]
    for row in c.execute("SELECT key,value FROM settings WHERE key LIKE ? ORDER BY key",(prefix+"%",)).fetchall():
        try:value=json.loads(row["value"])
        except Exception:continue
        if isinstance(value,dict):out.append(value)
    return out


def feedback_for_run(c,run_id:int)->dict[str,Any]|None:
    value=get_setting(c,feedback_key(run_id),None);return value if isinstance(value,dict) else None


def _same_day_run(c,scheduled_date:str):
    rows=c.execute("SELECT * FROM runs WHERE substr(started_at,1,10)=? ORDER BY started_at,id",(scheduled_date,)).fetchall();return rows[0] if len(rows)==1 else None


def save_workout_feedback(c,workout_id:int,*,rpe:int,legs:int,pain:str,recovery:int)->dict[str,Any]:
    w=c.execute("SELECT * FROM workouts WHERE id=?",(workout_id,)).fetchone()
    if not w:raise KeyError("Training nicht gefunden.")
    if w["status"]!="completed":raise ValueError("Feedback kann erst nach einer absolvierten Einheit gespeichert werden.")
    run=c.execute("SELECT * FROM runs WHERE id=?",(w["linked_run_id"],)).fetchone() if w["linked_run_id"] else _same_day_run(c,w["scheduled_date"])
    if not run:raise ValueError("Für diese Einheit ist noch kein eindeutiger Laufdatensatz verknüpft.")
    run_id=int(run["id"])
    if not w["linked_run_id"]:c.execute("UPDATE workouts SET linked_run_id=? WHERE id=?",(run_id,workout_id))
    payload={"schema":1,"run_id":run_id,"workout_id":int(workout_id),"date":str(run["started_at"])[:10],"rpe":int(rpe),"legs":int(legs),"pain":str(pain),"recovery":int(recovery),"created_at":datetime.now(timezone.utc).isoformat()}
    set_setting(c,feedback_key(run_id),payload);c.execute("UPDATE runs SET rpe=? WHERE id=?",(int(rpe),run_id));return payload


def _daily_metric(c,metric:str,start:date,end:date)->list[tuple[date,float]]:
    grouped={}
    for row in c.execute("SELECT start_at,value FROM health_metrics WHERE metric_type=? AND substr(start_at,1,10)>=? AND substr(start_at,1,10)<? ORDER BY start_at",(metric,start.isoformat(),end.isoformat())).fetchall():
        try:d=date.fromisoformat(str(row["start_at"])[:10]);grouped.setdefault(d,[]).append(float(row["value"]))
        except Exception:continue
    return [(d,statistics.mean(v)) for d,v in sorted(grouped.items()) if v]


def _trend_signal(c,metric:str,ref:date,higher_is_worse:bool):
    baseline=_daily_metric(c,metric,ref-timedelta(days=42),ref-timedelta(days=7));recent=_daily_metric(c,metric,ref-timedelta(days=7),ref+timedelta(days=1))
    if len(baseline)<10 or len(recent)<2:return None
    base_val=statistics.median(v for _,v in baseline);recent_val=statistics.mean(v for _,v in recent[-5:])
    if not base_val:return None
    delta=100*(recent_val-base_val)/abs(base_val);adverse=delta if higher_is_worse else -delta
    return {"baseline":round(base_val,2),"recent":round(recent_val,2),"delta_pct":round(delta,1),"adverse_pct":round(adverse,1),"recent_days":len(recent[-5:]),"baseline_days":len(baseline)}


def _sleep_signal(c,ref:date):
    baseline=_daily_metric(c,"sleep_hours",ref-timedelta(days=42),ref-timedelta(days=7));recent=_daily_metric(c,"sleep_hours",ref-timedelta(days=5),ref+timedelta(days=1))
    if len(baseline)<7 or not recent:return None
    b=statistics.median(v for _,v in baseline);r=statistics.mean(v for _,v in recent[-3:]);return {"baseline":round(b,2),"recent":round(r,2),"delta_hours":round(r-b,2),"recent_days":len(recent[-3:])}


def _recent_feedback(c,ref:date,days:int=7)->list[dict[str,Any]]:
    cutoff=ref-timedelta(days=days);out=[]
    for item in _json_setting_rows(c,"workout_feedback:"):
        try:d=date.fromisoformat(str(item.get("date",""))[:10])
        except Exception:continue
        if cutoff<=d<=ref:out.append(item)
    return sorted(out,key=lambda x:(x.get("date",""),int(x.get("run_id",0))))


def _latest_easy_hr_anomaly(c,ref:date):
    rows=c.execute("SELECT r.*,w.workout_type FROM runs r LEFT JOIN workouts w ON w.linked_run_id=r.id WHERE substr(r.started_at,1,10)>=? AND substr(r.started_at,1,10)<=? AND r.avg_hr IS NOT NULL AND r.duration_s>0 ORDER BY r.started_at DESC LIMIT 12",((ref-timedelta(days=28)).isoformat(),ref.isoformat())).fetchall();easy=[]
    for row in rows:
        if row["workout_type"] not in {None,"easy"}:continue
        easy.append((float(row["duration_s"])/max(float(row["distance_km"]),.1),float(row["avg_hr"]),str(row["started_at"])[:10]))
    if len(easy)<4:return None
    latest=easy[0];comparables=[x for x in easy[1:] if abs(x[0]-latest[0])/max(latest[0],1)<=.08]
    if len(comparables)<3:return None
    b=statistics.median(x[1] for x in comparables);delta=100*(latest[1]-b)/b;return {"latest_hr":round(latest[1],1),"baseline_hr":round(b,1),"delta_pct":round(delta,1),"date":latest[2]}


def recovery_state(c,ref:date|None=None)->RecoveryState:
    ref=ref or date.today();signals={};reasons=[];risk=0.
    hrv=_trend_signal(c,"hrv_sdnn",ref,False)
    if hrv:
        signals["hrv"]=hrv
        if hrv["adverse_pct"]>=12:risk+=1.5;reasons.append("HRV-Trend liegt deutlich unter der persönlichen 21–42-Tage-Baseline.")
        elif hrv["adverse_pct"]>=6:risk+=.75;reasons.append("HRV-Trend liegt etwas unter der persönlichen Baseline.")
    rhr=_trend_signal(c,"resting_hr",ref,True)
    if rhr:
        signals["resting_hr"]=rhr
        if rhr["adverse_pct"]>=8:risk+=1.5;reasons.append("Ruhepuls liegt über der persönlichen 21–42-Tage-Baseline.")
        elif rhr["adverse_pct"]>=4:risk+=.75;reasons.append("Ruhepuls ist gegenüber der persönlichen Baseline leicht erhöht.")
    sleep=_sleep_signal(c,ref)
    if sleep:
        signals["sleep"]=sleep
        if sleep["delta_hours"]<=-1.5:risk+=1.5;reasons.append("Schlafdauer liegt über mehrere Nächte deutlich unter der persönlichen Baseline.")
        elif sleep["delta_hours"]<=-.75:risk+=.75;reasons.append("Schlafdauer liegt zuletzt unter der persönlichen Baseline.")
    feedback=_recent_feedback(c,ref,7)
    if feedback:
        latest=feedback[-1];signals["subjective"]={"samples":len(feedback),"latest":latest,"avg_recovery":round(statistics.mean(int(x.get("recovery",3) or 3) for x in feedback[-3:]),2),"avg_legs":round(statistics.mean(int(x.get("legs",3) or 3) for x in feedback[-3:]),2)}
        pain=str(latest.get("pain","none"))
        if pain=="relevant":risk+=4;reasons.append("Du hast relevante Schmerzen gemeldet; die App reduziert nur Trainingsbelastung und stellt keine Diagnose.")
        elif pain=="light":risk+=1;reasons.append("Du hast leichte Beschwerden gemeldet.")
        if int(latest.get("legs",3) or 3)<=2:risk+=1.25;reasons.append("Die Beine wurden zuletzt als deutlich müde bewertet.")
        if int(latest.get("recovery",3) or 3)<=2:risk+=1.25;reasons.append("Die subjektive Erholung ist zuletzt niedrig.")
        if int(latest.get("rpe",6) or 6)>=9:risk+=.75;reasons.append("Die letzte Einheit wurde als sehr anstrengend bewertet.")
        good=[x for x in feedback[-4:] if int(x.get("recovery",3) or 3)>=4 and int(x.get("legs",3) or 3)>=3 and str(x.get("pain","none"))=="none" and int(x.get("rpe",6) or 6)<=7]
        if len(good)>=3:risk=max(0,risk-.75);reasons.append("Mehrere subjektive Rückmeldungen sprechen für gute Belastungsverträglichkeit.")
    anomaly=_latest_easy_hr_anomaly(c,ref)
    if anomaly:
        signals["easy_hr"]=anomaly
        if anomaly["delta_pct"]>=8:risk+=1;reasons.append("Bei vergleichbarer Easy-Pace war die Herzfrequenz zuletzt ungewöhnlich höher.")
    level=ReadinessLevel.RED if risk>=4 else ReadinessLevel.YELLOW if risk>=2 else ReadinessLevel.GREEN
    if not reasons:reasons.append("Keine deutliche Kombination negativer Recovery-Signale erkannt; einzelne Messwerte entscheiden nicht isoliert.")
    signals["data_note"]="HRV und Ruhepuls werden relativ zur persönlichen Baseline bewertet; keine medizinische Diagnose."
    return RecoveryState(level,risk,tuple(reasons),signals)


def _haversine(a,b)->float:
    lat1,lon1,lat2,lon2=map(math.radians,(float(a["latitude"]),float(a["longitude"]),float(b["latitude"]),float(b["longitude"])))
    dlat=lat2-lat1;dlon=lon2-lon1;q=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2;return 6371.0088*2*math.asin(min(1,math.sqrt(q)))


def run_response_metrics(c,run_id:int)->dict[str,Any]:
    run=c.execute("SELECT * FROM runs WHERE id=?",(run_id,)).fetchone()
    if not run:raise KeyError("Lauf nicht gefunden.")
    result={"run_id":int(run_id),"distance_km":float(run["distance_km"]),"duration_s":float(run["duration_s"]),"pace_s_per_km":round(float(run["duration_s"])/max(float(run["distance_km"]),.1),1),"avg_hr":float(run["avg_hr"]) if run["avg_hr"] is not None else None,"elevation_m":float(run["elevation_m"]) if run["elevation_m"] is not None else None,"rpe":int(run["rpe"]) if run["rpe"] is not None else None,"feedback":feedback_for_run(c,run_id)}
    by_type={};hr=[]
    for row in c.execute("SELECT metric_type,sampled_at,value,unit FROM run_samples WHERE run_id=? ORDER BY sampled_at,id",(run_id,)).fetchall():
        by_type.setdefault(str(row["metric_type"]),[]).append(float(row["value"]));
        if row["metric_type"]=="heart_rate":hr.append(float(row["value"]))
    result["sample_summary"]={k:{"average":round(statistics.mean(v),2),"minimum":round(min(v),2),"maximum":round(max(v),2),"samples":len(v)} for k,v in by_type.items() if v};result["sample_averages"]={k:v["average"] for k,v in result["sample_summary"].items()}
    speed=by_type.get("running_speed",[]);result["heart_rate_drift_pct_estimate"]=None
    if len(hr)>=8:
        mid=len(hr)//2;h1=statistics.mean(hr[:mid]);h2=statistics.mean(hr[mid:])
        if len(speed)>=8:
            smid=len(speed)//2;s1=statistics.mean(speed[:smid]);s2=statistics.mean(speed[smid:])
            if s1>0 and s2>0:
                e1=s1/max(h1,1);e2=s2/max(h2,1);result["heart_rate_drift_pct_estimate"]=round(100*(e1-e2)/max(abs(e1),1e-9),1);result["heart_rate_drift_note"]="Schätzung der aeroben Entkopplung aus Speed/Herzfrequenz der ersten und zweiten Hälfte; kein Labortest."
        else:result["heart_rate_drift_pct_estimate"]=round(100*(h2-h1)/max(h1,1),1);result["heart_rate_drift_note"]="HR-only-Schätzung aus erster/zweiter Hälfte; ohne Speed-Zeitreihe nicht als aerobe Entkopplung interpretieren."
    gps=c.execute("SELECT sampled_at,latitude,longitude,elevation_m,sequence FROM gps_points WHERE run_id=? ORDER BY sequence",(run_id,)).fetchall();result["gps_points"]=len(gps)
    if len(gps)>=2:
        cumulative=0.;next_km=1.;splits=[];gain=0.;prev=gps[0]
        try:split_start=base.parse_dt(str(prev["sampled_at"]))
        except Exception:split_start=None
        for point in gps[1:]:
            cumulative+=_haversine(prev,point)
            if prev["elevation_m"] is not None and point["elevation_m"] is not None:gain+=max(0,float(point["elevation_m"])-float(prev["elevation_m"]))
            while cumulative>=next_km and split_start is not None:
                try:stamp=base.parse_dt(str(point["sampled_at"]))
                except Exception:break
                sec=(stamp-split_start).total_seconds()
                if 60<=sec<=1800:splits.append({"km":int(next_km),"seconds":round(sec,1),"pace_s_per_km":round(sec,1)})
                split_start=stamp;next_km+=1
            prev=point
        result.update({"route_distance_km_estimate":round(cumulative,2),"elevation_gain_m_estimate":round(gain,1),"km_splits_estimate":splits[:60],"split_note":"Splits werden nur bei vorhandener GPS-Zeitreihe näherungsweise aus den Trackpunkten berechnet."})
    return result


def recent_run_responses(c,limit:int=6):
    ids=[int(r["id"]) for r in c.execute("SELECT id FROM runs ORDER BY started_at DESC LIMIT ?",(limit,)).fetchall()];return [run_response_metrics(c,rid) for rid in ids]


def _next_hard_workout(c,ref:date):
    for row in c.execute("SELECT * FROM workouts WHERE status='planned' AND scheduled_date>=? ORDER BY scheduled_date,id LIMIT 8",(ref.isoformat(),)).fetchall():
        try:details=json.loads(row["details_json"] or "{}")
        except Exception:details={}
        load=details.get("load") or {};hard=row["workout_type"]=="quality" or float(load.get("moderate_min",0) or 0)+float(load.get("high_min",0) or 0)>=18
        if hard:return row,details
    return None,None


def _pending_for_workout(c,wid:int)->bool:
    for row in c.execute("SELECT payload_json FROM suggestions WHERE status='pending' ORDER BY id DESC LIMIT 50").fetchall():
        try:p=json.loads(row["payload_json"] or "{}")
        except Exception:continue
        if int(p.get("workout_id",0) or 0)==int(wid):return True
    return False


def adaptation_suggestion(c,ref:date|None=None)->dict[str,Any]:
    ref=ref or date.today();readiness=recovery_state(c,ref);workout,_=_next_hard_workout(c,ref)
    if not workout:return {"readiness":readiness.as_dict(),"suggestion_id":None,"suggestion":None}
    wid=int(workout["id"])
    if _pending_for_workout(c,wid):return {"readiness":readiness.as_dict(),"suggestion_id":None,"suggestion":None,"note":"Für diese Einheit ist bereits ein Vorschlag offen."}
    current=float(workout["distance_km"]);change=title=rationale=None
    if readiness.level is ReadinessLevel.RED:
        proposed=round(max(3,current*.62),1)
        if proposed<current-.4:change={"distance_km":proposed};title="Qualitätsreiz deutlich reduzieren";rationale="Mehrere Recovery-Signale sind gemeinsam auffällig. Einzelne HRV-Werte entscheiden nicht isoliert; die Kombination spricht dafür, den nächsten harten Reiz deutlich zu verkürzen."
    elif readiness.level is ReadinessLevel.YELLOW:
        proposed=round(max(3,current*.84),1)
        if proposed<current-.4:change={"distance_km":proposed};title="Qualität leicht reduzieren";rationale="Die Recovery-Lage ist leicht auffällig. Eine kleine Dosisreduktion erhält den Trainingsreiz, ohne unnötig Ermüdung zu stapeln."
    else:
        feedback=_recent_feedback(c,ref,28);good=[x for x in feedback[-6:] if int(x.get("recovery",3) or 3)>=4 and int(x.get("legs",3) or 3)>=3 and str(x.get("pain","none"))=="none" and int(x.get("rpe",6) or 6)<=7]
        if len(good)>=4 and current>=8:
            proposed=round(min(current*1.08,current+2),1)
            if proposed>current+.4:change={"distance_km":proposed};title="Vorsichtige Progression möglich";rationale="Mehrere Einheiten wurden kontrolliert vertragen und die subjektive Erholung ist stabil. Eine kleine Progression ist möglich; schneller laufen ist dabei nicht automatisch das Ziel."
    if not change:return {"readiness":readiness.as_dict(),"suggestion_id":None,"suggestion":None}
    payload={"action":"update_workout","workout_id":wid,"changes":change};cur=c.execute("INSERT INTO suggestions(suggestion_type,title,rationale,payload_json) VALUES('adaptive_plan_change',?,?,?)",(title,rationale+" Du entscheidest, ob die Änderung übernommen wird.",json.dumps(payload,ensure_ascii=False)))
    return {"readiness":readiness.as_dict(),"suggestion_id":int(cur.lastrowid),"suggestion":{"title":title,"rationale":rationale,"workout_id":wid,"changes":change}}


def coach_context(c)->dict[str,Any]:
    return {"readiness":recovery_state(c).as_dict(),"recent_run_responses":recent_run_responses(c,6),"subjective_feedback":_recent_feedback(c,date.today(),28)[-8:]}
