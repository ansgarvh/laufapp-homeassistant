from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import training as base
from db import get_setting, set_setting
from training_adaptation_v020 import recovery_state
from training_models_v020 import PhysiologicalTarget, PlannedSession, RecoveryState, TrainingLoad, TrainingPhase, WeeklyPlanDecision, WorkoutType
from training_planner_v020 import automatic_max_weekly_km as science_auto_max, block_position, build_week_sessions, phase_for_week, projected_rolling_distribution, training_paces, weekly_target

VERSION = "0.2.0"


def _priority_map(c):
    raw=get_setting(c,"race_priorities",{}) or {}
    out={}
    for k,v in dict(raw).items():
        priority=str(v).upper()
        out[str(k)]=priority if priority in {"A","B","C"} else "A"
    return out

def race_priority(c,race_id:int)->str:return _priority_map(c).get(str(int(race_id)),"A")

def current_race(c,ref:date|None=None):
    ref=ref or date.today();priorities=_priority_map(c)
    for r in c.execute("SELECT * FROM races WHERE active=1 AND race_date>=? ORDER BY race_date,id",(ref.isoformat(),)).fetchall():
        if priorities.get(str(int(r["id"])),"A")=="A":return r
    return None

def race_for_week(c,ws:date):
    priorities=_priority_map(c)
    for r in c.execute("SELECT * FROM races WHERE active=1 AND race_date>=? ORDER BY race_date,id",(ws.isoformat(),)).fetchall():
        if priorities.get(str(int(r["id"])),"A")=="A":return r
    return None

def b_races_for_week(c,ws:date):
    end=ws+timedelta(days=6);priorities=_priority_map(c)
    return [r for r in c.execute("SELECT * FROM races WHERE active=1 AND race_date BETWEEN ? AND ? ORDER BY race_date,id",(ws.isoformat(),end.isoformat())).fetchall() if priorities.get(str(int(r["id"])),"A")=="B"]

def c_races_for_week(c,ws:date):
    end=ws+timedelta(days=6);priorities=_priority_map(c)
    return [r for r in c.execute("SELECT * FROM races WHERE active=1 AND race_date BETWEEN ? AND ? ORDER BY race_date,id",(ws.isoformat(),end.isoformat())).fetchall() if priorities.get(str(int(r["id"])),"A")=="C"]

def previous_a_race(c,ref:date):
    priorities=_priority_map(c)
    rows=c.execute("SELECT * FROM races WHERE active=1 AND race_date<? ORDER BY race_date DESC,id DESC",(ref.isoformat(),)).fetchall()
    return next((r for r in rows if priorities.get(str(int(r["id"])),"A")=="A"),None)


def _readiness(c,ws:date)->RecoveryState:
    # Future weeks use the latest known state. Existing weeks are never silently
    # regenerated after Health import; a refresh remains an explicit user action.
    return recovery_state(c,min(ws,date.today()))

def _phase(race,ws:date):
    p,w=phase_for_week(race,ws);return p.value,w

def _block_state(race,ws:date,phase:str):
    try:p=TrainingPhase(phase)
    except ValueError:p=TrainingPhase.BUILD
    pos,cycle=block_position(race,ws,p);return {"cycle":cycle or None,"position":pos if cycle else None,"recovery":bool(cycle and pos==0)}

def _weekly_target(c,race,ws:date):
    readiness=_readiness(c,ws)
    total,phase=weekly_target(c,race,ws,readiness)
    previous=previous_a_race(c,ws)
    if previous and phase is not TrainingPhase.RACE:
        days_since=(ws-date.fromisoformat(previous["race_date"])).days
        days_to_next=(date.fromisoformat(race["race_date"])-ws).days
        prefs=base._prefs(c,float(race["distance_km"]))
        established=float(base.established_volume(c,ws)["km"] or prefs["baseline"])
        if 1<=days_since<=7:
            phase=TrainingPhase.RECOVERY
            total=min(total,max(14.0,established*.58))
        elif 8<=days_since<=14:
            if days_to_next<=14:
                phase=TrainingPhase.TAPER
                total=min(total,max(14.0,established*.62))
            else:
                phase=TrainingPhase.RECOVERY
                total=min(total,max(14.0,established*.72))
    return round(total,1),phase.value

def automatic_max_weekly_km(c,race=None,ref:date|None=None):
    race=race or current_race(c,ref);return science_auto_max(c,race,ref,_readiness(c,ref or date.today()))


def _configured_dates(c,ws:date)->list[date]:
    days=sorted(set(int(x) for x in get_setting(c,"training_days",[1,3,4,6]) if 0<=int(x)<=6));days=days if 3<=len(days)<=7 else [1,3,4,6];return [ws+timedelta(days=d) for d in days]


def _race_load(distance:float,goal_seconds:float,priority:str)->TrainingLoad:
    duration=goal_seconds/60;ratio=goal_seconds/max(distance,.1)
    if distance<=10:high,moderate=duration*.72,duration*.18
    elif distance<=25:high,moderate=duration*.25,duration*.60
    else:high,moderate=duration*.10,duration*.70
    if priority=="C":high*=.72;moderate*=.90
    low=max(0,duration-high-moderate)
    rpe=9 if priority=="B" else 7.5
    return TrainingLoad(distance,duration,"race",low,moderate,high,moderate+high,moderate,high,0,0,0,rpe,round(low+1.65*moderate+2.35*high+24,1))

def _b_race_session(c,b,original_long:PlannedSession)->PlannedSession:
    distance=float(b["distance_km"]);goal=float(b["goal_seconds"]);goal_pace=goal/max(distance,.1);load=_race_load(distance,goal,"B")
    return PlannedSession("race",f"B-RENNEN · {b['name']}",distance,"b_race","Wettkampf","B-Rennen","Wettkampf kontrolliert laufen; keine zusätzliche harte Ersatz-Einheit in derselben Woche.",PhysiologicalTarget.RACE,"b_race",WorkoutType.RACE.value,load,"Das B-Rennen ersetzt ausschließlich den Longrun dieser Woche. Die übrige Periodisierung bleibt auf das A-Rennen ausgerichtet.",{"replaced_long_run_km":original_long.distance_km,"goal_pace_s_per_km":round(goal_pace,1)})

def _c_race_session(c,race,replaced:PlannedSession)->PlannedSession:
    distance=float(race["distance_km"]);goal=float(race["goal_seconds"]);goal_pace=goal/max(distance,.1);load=_race_load(distance,goal,"C")
    return PlannedSession("race",f"C-RENNEN · {race['name']}",distance,"c_race","7–8/10","C-Rennen","Als kontrollierten Trainingswettkampf laufen. Kein zusätzlicher Taper und kein All-out-Zwang.",PhysiologicalTarget.RACE,"c_race",WorkoutType.RACE.value,load,"Das C-Rennen ersetzt nur eine strukturierte Einheit seiner Rennwoche. Der A-Rennen-Aufbau und der Longrun bleiben ansonsten unverändert.",{"replaced_workout_type":replaced.workout_type,"replaced_workout_km":replaced.distance_km,"goal_pace_s_per_km":round(goal_pace,1)})

def _week_sessions(c,race,ws:date,phase:str,total:float):
    readiness=_readiness(c,ws)
    try:phase_enum=TrainingPhase(phase)
    except ValueError:phase_enum=phase_for_week(race,ws)[0]
    decision=build_week_sessions(c,race,ws,total,phase_enum,readiness);sessions=list(decision.sessions);dates=_configured_dates(c,ws);paces=training_paces(c,race)
    zones={"easy":paces["easy"],"steady":paces["steady"],"marathon":paces["marathon"],"goal":paces["marathon"],"threshold":paces["threshold"],"interval":paces["interval"]};equivalent_by_title={};secondary_meta=None
    b_races=b_races_for_week(c,ws);c_races=c_races_for_week(c,ws)
    if b_races and phase_enum is not TrainingPhase.RACE:
        b=b_races[0];replace_idx=next((i for i,s in enumerate(sessions) if s.workout_type=="long"),None)
        priority="B"
    elif c_races and phase_enum is not TrainingPhase.RACE:
        b=c_races[0];replace_idx=next((i for i,s in enumerate(sessions) if s.workout_type=="quality"),None)
        if replace_idx is None:replace_idx=next((i for i,s in enumerate(sessions) if s.workout_type=="easy"),None)
        priority="C"
    else:
        b=None;replace_idx=None;priority=None
    if b is not None and replace_idx is not None:
        original=sessions[replace_idx];original_date=dates[replace_idx];race_day=date.fromisoformat(b["race_date"]);collision=next((i for i,d in enumerate(dates) if i!=replace_idx and d==race_day),None)
        if collision is not None:dates[collision]=original_date
        dates[replace_idx]=race_day
        race_session=_b_race_session(c,b,original) if priority=="B" else _c_race_session(c,b,original)
        sessions[replace_idx]=race_session;zone_key="b_race" if priority=="B" else "c_race"
        zones[zone_key]=(float(b["goal_seconds"])/float(b["distance_km"])-5,float(b["goal_seconds"])/float(b["distance_km"])+5)
        equivalent_by_title[race_session.title]=original.distance_km
        secondary_meta={"id":int(b["id"]),"name":b["name"],"race_date":b["race_date"],"distance_km":float(b["distance_km"]),"goal_seconds":int(b["goal_seconds"]),"priority":priority,"replaced_km":round(original.distance_km,1),"replaced_workout_type":original.workout_type}
    decision=WeeklyPlanDecision(tuple(sessions),decision.phase,decision.readiness,projected_rolling_distribution(c,ws,sessions),decision.physiological_focus)
    return dates,sessions,zones,equivalent_by_title,secondary_meta,decision

def plan_basis(c,ws,race,total,phase):
    ev=base.established_volume(c,ws);lh=base.long_run_history(c,ws);weeks=max(0,(date.fromisoformat(race["race_date"])-ws).days//7);core=phase_for_week(race,ws)[0];block=_block_state(race,ws,core.value);b=b_races_for_week(c,ws);cr=c_races_for_week(c,ws);readiness=_readiness(c,ws);paces=training_paces(c,race);previous=previous_a_race(c,ws)
    days_since_previous=(ws-date.fromisoformat(previous["race_date"])).days if previous else None
    return {"established_weekly_km":ev["km"] or base._prefs(c,float(race["distance_km"]))["baseline"],"trend":ev["trend"],"longest_recent_km":lh["longest_8w"],"phase":phase,"weeks_to_race":weeks,"planned_weekly_km":round(total,1),"current_partial_km":ev["current_partial_km"],"focus_race_id":int(race["id"]),"focus_race_name":race["name"],"block_position":block["position"],"block_cycle":block["cycle"],"readiness":readiness.as_dict(),"training_paces":{k:v for k,v in paces.items() if not isinstance(v,tuple)},"b_race":{"id":int(b[0]["id"]),"name":b[0]["name"],"race_date":b[0]["race_date"]} if b else None,"c_race":{"id":int(cr[0]["id"]),"name":cr[0]["name"],"race_date":cr[0]["race_date"]} if cr else None,"previous_a_race":{"id":int(previous["id"]),"name":previous["name"],"race_date":previous["race_date"],"days_since":days_since_previous} if previous and days_since_previous is not None and days_since_previous<=14 else None}


def _scaled_load_dict(load:TrainingLoad,factor:float)->dict:
    factor=max(0,min(1,float(factor)));data=load.as_dict()
    for key in ("distance_km","duration_min","low_min","moderate_min","high_min","above_lt1_min","around_lt2_min","above_lt2_min","marathon_pace_min","elevation_m","long_run_duration_min","score"):data[key]=round(float(data.get(key,0) or 0)*factor,2)
    return data


def _session_lookup(templates,sessions):
    pairs=[{"template":t,"session":s,"used":False} for t,s in zip(templates,sessions)]
    def take(template):
        for item in pairs:
            if not item["used"] and item["template"]==template:item["used"]=True;return item["session"]
        for item in pairs:
            if not item["used"] and item["template"][0]==template[0] and item["template"][1]==template[1]:item["used"]=True;return item["session"]
        return None
    return take


def generate_week(c,ws:date|None=None,force=False):
    ws=base.week_start_for(ws or date.today());key=ws.isoformat();removed=base._cleanup_generated_collisions(c,ws);existing=c.execute("SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id",(key,)).fetchall();native=c.execute("SELECT * FROM workouts WHERE origin_week_start=? ORDER BY scheduled_date,id",(key,)).fetchall()
    if native and not force and not removed:return [base._wdict(r) for r in existing]
    race=race_for_week(c,ws)
    if not race:return [base._wdict(r) for r in existing]
    if force:
        c.execute("DELETE FROM workouts WHERE origin_week_start=? AND scheduled_date>=? AND status='planned' AND linked_run_id IS NULL AND COALESCE(manual_override,0)=0",(key,date.today().isoformat()));c.execute("DELETE FROM plan_reviews WHERE week_start=?",(key,))
    native_rows=c.execute("SELECT * FROM workouts WHERE origin_week_start=? ORDER BY scheduled_date,id",(key,)).fetchall();total,phase=_weekly_target(c,race,ws);dates,sessions,zones,equivalent,secondary_meta,decision=_week_sessions(c,race,ws,phase,total);templates=[s.legacy_tuple() for s in sessions];take=_session_lookup(templates,sessions)
    remaining=base._remaining_template_slots(dates,templates,native_rows);visible=c.execute("SELECT * FROM workouts WHERE scheduled_date BETWEEN ? AND ? ORDER BY scheduled_date,id",(key,(ws+timedelta(days=6)).isoformat())).fetchall();occupied={r["scheduled_date"] for r in visible};preserved=sum(float(r["distance_km"] or 0) for r in visible);candidates=base._schedule_remaining_slots(ws,remaining,occupied)
    equivalent_candidate=sum(float(equivalent.get(t[1],t[2])) for _,t in candidates);remaining_km=max(0,total-preserved);scale=min(1,remaining_km/equivalent_candidate) if equivalent_candidate>0 else 0;generation=datetime.now(timezone.utc).isoformat();basis=plan_basis(c,ws,race,total,phase)
    for scheduled,t in candidates:
        typ,title,km,zone,rpe,purpose,instructions=t;session=take(t);fixed=title in equivalent;effective=float(km) if fixed else float(km)*scale
        if effective<=.05:continue
        low,high=zones.get(zone,(None,None));dose=1 if fixed else effective/max(float(km),.001)
        details={"purpose":purpose,"instructions":instructions,"phase":phase,"week_target_km":round(total,1),"rpe_target":rpe,"plan_basis":basis,"physiological_target":session.target.value if session else None,"variant_key":session.variant_key if session else None,"workout_form":session.display_kind if session else typ,"why":session.why if session else purpose,"load":_scaled_load_dict(session.load,dose) if session else {},"load_model":"planning_estimate_v1","rolling_intensity_distribution":decision.intensity_distribution,"physiological_focus":decision.physiological_focus}
        if session:
            details.update(session.metadata);details["mp_km"]=round(float(session.metadata.get("mp_km",0) or 0)*dose,2)
        if typ=="race":
            if fixed and secondary_meta:
                details.update({"race_id":secondary_meta["id"],"race_priority":secondary_meta["priority"],"goal_seconds":secondary_meta["goal_seconds"],"replaced_workout_km":secondary_meta["replaced_km"],"replaced_workout_type":secondary_meta["replaced_workout_type"]})
                if secondary_meta["priority"]=="B":details["replaced_long_run_km"]=secondary_meta["replaced_km"]
            else:details.update({"race_id":int(race["id"]),"race_priority":"A","goal_seconds":int(race["goal_seconds"])})
        c.execute("INSERT INTO workouts(week_start,origin_week_start,scheduled_date,workout_type,title,distance_km,pace_low_s_per_km,pace_high_s_per_km,details_json,status,manual_override,modified_by,generation_version,plan_generation_id) VALUES(?,?,?,?,?,?,?,?,?,'planned',0,'engine',?,?)",(key,key,scheduled.isoformat(),typ,title,round(effective,1),low,high,json.dumps(details,ensure_ascii=False),VERSION,generation))
    if force:set_setting(c,"plan_stale",False);set_setting(c,"plan_stale_reason","")
    return [base._wdict(r) for r in c.execute("SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id",(key,)).fetchall()]


def refresh_plan(c,start:date|None=None,weeks=4):
    start=base.week_start_for(start or date.today());old=[]
    for i in range(weeks):
        ws=start+timedelta(days=7*i);base._cleanup_generated_collisions(c,ws);rows0=[base._wdict(r) for r in c.execute("SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id",(ws.isoformat(),)).fetchall()]
        if i==0:old=rows0
        generate_week(c,ws,True)
    new=[base._wdict(r) for r in c.execute("SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id",(start.isoformat(),)).fetchall()]
    def stats(xs):return (round(sum(float(x["distance_km"]) for x in xs),1),max([float(x["distance_km"]) for x in xs if x["workout_type"] in {"long","race"}] or [0]),next((x["title"] for x in xs if x["workout_type"]=="quality"),None))
    a,b=stats(old),stats(new);diff={}
    if a[0]!=b[0]:diff["volume_km"]={"old":a[0],"new":b[0]}
    if a[1]!=b[1]:diff["long_run_km"]={"old":a[1],"new":b[1]}
    if a[2]!=b[2]:diff["quality"]={"old":a[2],"new":b[2]}
    if len(old)!=len(new):diff["session_count"]={"old":len(old),"new":len(new)}
    return {"updated":bool(diff),"diff":diff,"weeks":weeks,"summary_week_start":start.isoformat()}


def _science_guardrails(c,workouts,ws:date):
    g=base.guardrails(c,workouts);loads=[(w.get("details") or {}).get("load") for w in workouts if (w.get("details") or {}).get("load")]
    if loads:
        low=sum(float(x.get("low_min",0) or 0) for x in loads);mod=sum(float(x.get("moderate_min",0) or 0) for x in loads);high=sum(float(x.get("high_min",0) or 0) for x in loads);total=low+mod+high
        if total:g["week_intensity_distribution"]={"low_pct":round(low/total*100,1),"moderate_pct":round(mod/total*100,1),"high_pct":round(high/total*100,1)}
    race=race_for_week(c,ws)
    if race:
        sums={"low":0.,"moderate":0.,"high":0.}
        for row in c.execute("SELECT details_json FROM workouts WHERE scheduled_date>=? AND scheduled_date<?",((ws-timedelta(days=21)).isoformat(),ws.isoformat())).fetchall():
            try:load=json.loads(row["details_json"] or "{}").get("load") or {}
            except Exception:continue
            for k in sums:sums[k]+=float(load.get(k+"_min",0) or 0)
        for load in loads:
            for k in sums:sums[k]+=float(load.get(k+"_min",0) or 0)
        denom=sum(sums.values());rolling={"low_pct":round(100*sums["low"]/denom,1) if denom else 0,"moderate_pct":round(100*sums["moderate"]/denom,1) if denom else 0,"high_pct":round(100*sums["high"]/denom,1) if denom else 0,"weeks":4};g["rolling_intensity_distribution"]=rolling;g["low_intensity_distance_share"]=rolling["low_pct"]/100
        if denom and rolling["low_pct"]<70:g.setdefault("alerts",[]).append({"level":"info","text":f"Rollierend über vier Wochen liegen nur {rolling['low_pct']:.0f}% der geschätzten Trainingszeit niedrigintensiv. Die nächste Planung sollte den Easy-Anteil priorisieren."});g["needs_review"]=True
        p=training_paces(c,race);g.update({"training_marathon_pace_s_per_km":p["training_marathon_pace_s_per_km"],"goal_marathon_pace_s_per_km":p["goal_marathon_pace_s_per_km"],"current_estimated_marathon_pace_s_per_km":p["current_estimated_marathon_pace_s_per_km"]})
    return g


def week_summary(c,ws):
    workouts=generate_week(c,ws);planned=sum(float(w["distance_km"]) for w in workouts);race=race_for_week(c,ws);total,phase=_weekly_target(c,race,ws) if race else (planned,"build");basis=plan_basis(c,ws,race,total,phase) if race else None;actual=float(c.execute("SELECT COALESCE(SUM(distance_km),0) km FROM runs WHERE started_at>=? AND started_at<?",(ws.isoformat(),(ws+timedelta(days=7)).isoformat())).fetchone()["km"] or 0)
    return {"week_start":ws.isoformat(),"week_end":(ws+timedelta(days=6)).isoformat(),"workouts":workouts,"planned_km":round(planned,1),"completed_planned_km":round(sum(float(w["distance_km"]) for w in workouts if w["status"]=="completed"),1),"actual_km":round(actual,1),"guardrails":_science_guardrails(c,workouts,ws),"plan_basis":basis,"plan_stale":bool(get_setting(c,"plan_stale",False)),"plan_stale_reason":get_setting(c,"plan_stale_reason","")}


def dashboard(c):
    race=current_race(c);today=date.today();week=week_summary(c,base.week_start_for(today)) if race else {"workouts":[],"planned_km":0,"actual_km":0};n=next((w for w in week["workouts"] if w["status"]=="planned" and w["scheduled_date"]>=today.isoformat()),None)
    return {"today":today.isoformat(),"race":dict(race) if race else None,"assessment":base.goal_assessment(c,race) if race else None,"next_workout":n,"week":week,"profile":base.performance_profile(c,race),"readiness":_readiness(c,today).as_dict(),"pending_suggestions":c.execute("SELECT COUNT(*) n FROM suggestions WHERE status='pending'").fetchone()["n"]}
