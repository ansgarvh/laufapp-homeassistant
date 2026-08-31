from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import training as base
from db import get_setting, set_setting
from training_adaptation_v020 import recovery_state
from training_models_v020 import PhysiologicalTarget, PlannedSession, RecoveryState, TrainingLoad, TrainingPhase, WeeklyPlanDecision, WorkoutType
from training_planner_v020 import automatic_max_weekly_km as science_auto_max, block_position, build_week_sessions, easy_session, phase_for_week, projected_rolling_distribution, training_paces, weekly_target

VERSION = "0.2.0"


def _priority_map(c):
    """Return normalized A/B/C priorities without changing stored user data."""
    raw=get_setting(c,"race_priorities",{}) or {}
    out={}
    for key,value in dict(raw).items():
        priority=str(value).upper()
        out[str(key)]=priority if priority in {"A","B","C"} else "A"
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

def support_races_for_week(c,ws:date,priority:str|None=None):
    """Return non-A races in a week. B/C never steer preceding periodization."""
    end=ws+timedelta(days=6);priorities=_priority_map(c);wanted=priority.upper() if priority else None
    rows=c.execute("SELECT * FROM races WHERE active=1 AND race_date BETWEEN ? AND ? ORDER BY race_date,id",(ws.isoformat(),end.isoformat())).fetchall()
    return [r for r in rows if (p:=priorities.get(str(int(r["id"])),"A")) in {"B","C"} and (wanted is None or p==wanted)]

def b_races_for_week(c,ws:date):
    return support_races_for_week(c,ws,"B")

def c_races_for_week(c,ws:date):
    return support_races_for_week(c,ws,"C")

def previous_a_race(c,ref:date):
    priorities=_priority_map(c)
    for r in c.execute("SELECT * FROM races WHERE active=1 AND race_date<? ORDER BY race_date DESC,id DESC",(ref.isoformat(),)).fetchall():
        if priorities.get(str(int(r["id"])),"A")=="A":return r
    return None

def _race_transition(c,ws:date,next_race):
    """Describe short post-A recovery/re-entry before the next A-race.

    The previous A-race never changes which race owns a future week. It only
    limits load for the first days after a demanding A-race. Marathon recovery
    is deliberately strongest; shorter A-races rely mostly on normal readiness.
    """
    previous=previous_a_race(c,ws)
    if not previous or int(previous["id"])==int(next_race["id"]):return None
    previous_date=date.fromisoformat(previous["race_date"]);days_after=(ws-previous_date).days
    if days_after<0:return None
    previous_distance=float(previous["distance_km"]);next_date=date.fromisoformat(next_race["race_date"]);days_to_next=(next_date-ws).days
    if previous_distance>=40 and days_after<=7:
        return {"mode":"post_a_recovery","factor":.50,"phase":"recovery","easy_only":True,"previous_race_id":int(previous["id"]),"previous_race_name":previous["name"],"previous_race_date":previous["race_date"],"days_after_previous":days_after,"days_to_next":days_to_next}
    if previous_distance>=40 and days_after<=14:
        return {"mode":"post_a_reentry","factor":.72,"phase":"taper" if days_to_next<=14 else "recovery","easy_only":False,"previous_race_id":int(previous["id"]),"previous_race_name":previous["name"],"previous_race_date":previous["race_date"],"days_after_previous":days_after,"days_to_next":days_to_next}
    if previous_distance>=20 and days_after<=7:
        return {"mode":"post_a_reentry","factor":.70,"phase":"taper" if days_to_next<=14 else "recovery","easy_only":False,"previous_race_id":int(previous["id"]),"previous_race_name":previous["name"],"previous_race_date":previous["race_date"],"days_after_previous":days_after,"days_to_next":days_to_next}
    return None

def _cleanup_generated_collisions_from(c,ws:date,cutoff:date)->int:
    """v0.1.8 collision repair, but never mutate dates before cutoff."""
    start=base.week_start_for(ws);end=start+timedelta(days=6);removed=0;groups={}
    first=max(start,cutoff)
    if first>end:return 0
    for r in c.execute("SELECT * FROM workouts WHERE scheduled_date BETWEEN ? AND ? ORDER BY id",(first.isoformat(),end.isoformat())).fetchall():groups.setdefault(r["scheduled_date"],[]).append(r)
    for group in groups.values():
        if len(group)<2:continue
        protected=[r for r in group if r["status"]!="planned" or r["linked_run_id"] is not None or int(r["manual_override"] or 0)!=0 or (r["modified_by"] or "engine")!="engine"]
        generated=[r for r in group if r["status"]=="planned" and r["linked_run_id"] is None and int(r["manual_override"] or 0)==0 and (r["modified_by"] or "engine")=="engine"]
        if protected and generated:
            c.executemany("DELETE FROM workouts WHERE id=?",[(int(r["id"]),) for r in generated]);removed+=len(generated)
    return removed

def replan_existing_future_weeks(c,cutoff:date|None=None):
    """Re-align already materialized plan weeks from today onward only.

    Unseen future weeks remain lazy and automatically use race_for_week when
    opened. Historical rows are intentionally not regenerated or cleaned up.
    """
    cutoff=cutoff or date.today();current_ws=base.week_start_for(cutoff)
    week_keys={str(r["origin_week_start"]) for r in c.execute("SELECT DISTINCT origin_week_start FROM workouts WHERE scheduled_date>=? AND origin_week_start IS NOT NULL",(cutoff.isoformat(),)).fetchall() if r["origin_week_start"]}
    if c.execute("SELECT 1 FROM workouts WHERE week_start=? LIMIT 1",(current_ws.isoformat(),)).fetchone():week_keys.add(current_ws.isoformat())
    replanned=[]
    for key in sorted(week_keys):
        try:ws=date.fromisoformat(key)
        except ValueError:continue
        if ws+timedelta(days=6)<cutoff:continue
        generate_week(c,ws,True);replanned.append(key)
    set_setting(c,"plan_stale",False);set_setting(c,"plan_stale_reason","")
    return replanned


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
    total,phase=weekly_target(c,race,ws,_readiness(c,ws));transition=_race_transition(c,ws,race)
    if phase is TrainingPhase.RACE:
        # Preserve the full target-race distance plus a small activation/easy
        # allowance; otherwise generic weekly scaling could shorten an HM/10k.
        total=max(total,float(race["distance_km"])+(8.0 if float(race["distance_km"])>=20 else 7.0))
    if not transition:return round(total,1),phase.value
    prefs=base._prefs(c,float(race["distance_km"]));established=float(base.established_volume(c,ws)["km"] or prefs["baseline"])
    transition_total=max(8.0,established*float(transition["factor"]))
    # A close second A-race may already imply an even smaller taper target.
    if transition["phase"]=="taper":transition_total=min(transition_total,total)
    return round(transition_total,1),transition["phase"]

def automatic_max_weekly_km(c,race=None,ref:date|None=None):
    race=race or current_race(c,ref);return science_auto_max(c,race,ref,_readiness(c,ref or date.today()))


def _configured_dates(c,ws:date)->list[date]:
    days=sorted(set(int(x) for x in get_setting(c,"training_days",[1,3,4,6]) if 0<=int(x)<=6));days=days if 3<=len(days)<=7 else [1,3,4,6];return [ws+timedelta(days=d) for d in days]


def _b_race_session(c,b,original_long:PlannedSession)->PlannedSession:
    distance=float(b["distance_km"]);duration=float(b["goal_seconds"])/60;goal_pace=float(b["goal_seconds"])/max(distance,.1)
    if distance<=10:high,moderate=duration*.72,duration*.18
    elif distance<=25:high,moderate=duration*.25,duration*.60
    else:high,moderate=duration*.10,duration*.70
    low=max(0,duration-high-moderate);load=TrainingLoad(distance,duration,"race",low,moderate,high,moderate+high,moderate,high,0,0,0,9,round(low+1.65*moderate+2.35*high+24,1))
    return PlannedSession("race",f"B-RENNEN · {b['name']}",distance,"b_race","Wettkampf","B-Rennen","Wettkampf kontrolliert laufen; keine zusätzliche harte Ersatz-Einheit in derselben Woche.",PhysiologicalTarget.RACE,"b_race",WorkoutType.RACE.value,load,"Das B-Rennen ersetzt ausschließlich den Longrun dieser Woche. Die übrige Periodisierung bleibt auf das A-Rennen ausgerichtet.",{"replaced_long_run_km":original_long.distance_km,"goal_pace_s_per_km":round(goal_pace,1)})

def _c_race_session(c,race,original:PlannedSession)->PlannedSession:
    distance=float(race["distance_km"]);duration=float(race["goal_seconds"])/60;goal_pace=float(race["goal_seconds"])/max(distance,.1)
    if distance<=10:high,moderate=duration*.68,duration*.22
    elif distance<=25:high,moderate=duration*.22,duration*.62
    else:high,moderate=duration*.08,duration*.72
    low=max(0,duration-high-moderate);load=TrainingLoad(distance,duration,"race",low,moderate,high,moderate+high,moderate,high,0,0,0,8.5,round(low+1.65*moderate+2.35*high+20,1))
    return PlannedSession("race",f"C-RENNEN · {race['name']}",distance,"c_race","Wettkampf","C-Rennen","Als Trainingswettkampf laufen; keine zusätzliche harte Einheit als Ersatz nachholen.",PhysiologicalTarget.RACE,"c_race",WorkoutType.RACE.value,load,"Das C-Rennen dient als Trainingsreiz und ersetzt in dieser Woche eine passende harte beziehungsweise lange Einheit. Die A-Rennen-Periodisierung davor bleibt unverändert.",{"replaced_session_km":original.distance_km,"goal_pace_s_per_km":round(goal_pace,1)})


def _week_sessions(c,race,ws:date,phase:str,total:float):
    readiness=_readiness(c,ws);transition=_race_transition(c,ws,race)
    try:phase_enum=TrainingPhase(phase)
    except ValueError:phase_enum=phase_for_week(race,ws)[0]
    dates=_configured_dates(c,ws);paces=training_paces(c,race);zones={"easy":paces["easy"],"steady":paces["steady"],"marathon":paces["marathon"],"goal":paces["marathon"],"a_race":(float(race["goal_seconds"])/float(race["distance_km"])-5,float(race["goal_seconds"])/float(race["distance_km"])+5),"threshold":paces["threshold"],"interval":paces["interval"]};equivalent_by_title={};support_meta=None
    if transition and transition.get("easy_only"):
        count=max(2,min(3,len(dates)));distance=max(3.0,total/count);sessions=[easy_session(c,race,distance,i,TrainingPhase.RECOVERY) for i in range(count)]
        decision=WeeklyPlanDecision(tuple(sessions),TrainingPhase.RECOVERY,readiness,projected_rolling_distribution(c,ws,sessions),"Erholung nach A-Rennen")
        return dates[:count],sessions,zones,equivalent_by_title,support_meta,decision
    decision=build_week_sessions(c,race,ws,total,phase_enum,readiness);sessions=list(decision.sessions)
    if phase_enum is TrainingPhase.RACE:
        race_idx=next((i for i,session in enumerate(sessions) if session.workout_type=="race"),None)
        if race_idx is not None:
            race_day=date.fromisoformat(race["race_date"]);original_date=dates[race_idx];collision=next((i for i,d in enumerate(dates) if i!=race_idx and d==race_day),None)
            if collision is not None:dates[collision]=original_date
            dates[race_idx]=race_day;equivalent_by_title[sessions[race_idx].title]=sessions[race_idx].distance_km
    support=support_races_for_week(c,ws)
    if support and phase_enum is not TrainingPhase.RACE:
        r=support[0];priority=race_priority(c,int(r["id"]));race_day=date.fromisoformat(r["race_date"]);distance=float(r["distance_km"])
        if priority=="B":replace_idx=next((i for i,s in enumerate(sessions) if s.workout_type=="long"),None)
        else:
            # Short C-races are quality sessions; long C-races replace the Long Run
            # to avoid stacking two large stressors in one training week.
            replace_idx=next((i for i,s in enumerate(sessions) if s.workout_type=="quality"),None) if distance<=15 else next((i for i,s in enumerate(sessions) if s.workout_type=="long"),None)
            if replace_idx is None:replace_idx=next((i for i,s in enumerate(sessions) if s.workout_type=="easy"),None)
        if replace_idx is not None:
            original=sessions[replace_idx];original_date=dates[replace_idx];collision=next((i for i,d in enumerate(dates) if i!=replace_idx and d==race_day),None)
            if collision is not None:dates[collision]=original_date
            dates[replace_idx]=race_day
            race_session=_b_race_session(c,r,original) if priority=="B" else _c_race_session(c,r,original);sessions[replace_idx]=race_session;zones[f"{priority.lower()}_race"]=(float(r["goal_seconds"])/distance-5,float(r["goal_seconds"])/distance+5);equivalent_by_title[race_session.title]=original.distance_km
            support_meta={"id":int(r["id"]),"name":r["name"],"race_date":r["race_date"],"distance_km":distance,"goal_seconds":int(r["goal_seconds"]),"priority":priority,"replaced_session_km":round(original.distance_km,1),"replaced_session_type":original.workout_type,"replaced_long_run_km":round(original.distance_km,1) if priority=="B" else None}
    decision=WeeklyPlanDecision(tuple(sessions),decision.phase,decision.readiness,projected_rolling_distribution(c,ws,sessions),decision.physiological_focus)
    return dates,sessions,zones,equivalent_by_title,support_meta,decision

def plan_basis(c,ws,race,total,phase):
    ev=base.established_volume(c,ws);lh=base.long_run_history(c,ws);weeks=max(0,(date.fromisoformat(race["race_date"])-ws).days//7);core=phase_for_week(race,ws)[0];block=_block_state(race,ws,core.value);support=support_races_for_week(c,ws);readiness=_readiness(c,ws);paces=training_paces(c,race);transition=_race_transition(c,ws,race)
    return {"established_weekly_km":ev["km"] or base._prefs(c,float(race["distance_km"]))["baseline"],"trend":ev["trend"],"longest_recent_km":lh["longest_8w"],"phase":phase,"weeks_to_race":weeks,"planned_weekly_km":round(total,1),"current_partial_km":ev["current_partial_km"],"focus_race_id":int(race["id"]),"focus_race_name":race["name"],"focus_race_priority":"A","block_position":block["position"],"block_cycle":block["cycle"],"readiness":readiness.as_dict(),"training_paces":{k:v for k,v in paces.items() if not isinstance(v,tuple)},"support_race":{"id":int(support[0]["id"]),"name":support[0]["name"],"race_date":support[0]["race_date"],"priority":race_priority(c,int(support[0]["id"]))} if support else None,"race_transition":transition}


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
    today=date.today();ws=base.week_start_for(ws or today);key=ws.isoformat();existing=c.execute("SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id",(key,)).fetchall()
    # Hard history boundary: race/calendar changes may never mutate a completed
    # calendar week. The current week is only editable from today forward.
    if ws+timedelta(days=6)<today:return [base._wdict(r) for r in existing]
    removed=_cleanup_generated_collisions_from(c,ws,today);native=c.execute("SELECT * FROM workouts WHERE origin_week_start=? ORDER BY scheduled_date,id",(key,)).fetchall()
    if native and not force and not removed:return [base._wdict(r) for r in existing]
    race=race_for_week(c,ws)
    if not race:return [base._wdict(r) for r in existing]
    if force:
        c.execute("DELETE FROM workouts WHERE origin_week_start=? AND scheduled_date>=? AND status='planned' AND linked_run_id IS NULL AND COALESCE(manual_override,0)=0",(key,today.isoformat()))
        if ws>=today:c.execute("DELETE FROM plan_reviews WHERE week_start=?",(key,))
    native_rows=c.execute("SELECT * FROM workouts WHERE origin_week_start=? ORDER BY scheduled_date,id",(key,)).fetchall();total,phase=_weekly_target(c,race,ws);dates,sessions,zones,equivalent,support_meta,decision=_week_sessions(c,race,ws,phase,total);templates=[s.legacy_tuple() for s in sessions];take=_session_lookup(templates,sessions)
    remaining=[(d,t) for d,t in base._remaining_template_slots(dates,templates,native_rows) if d>=today];visible=c.execute("SELECT * FROM workouts WHERE scheduled_date BETWEEN ? AND ? ORDER BY scheduled_date,id",(key,(ws+timedelta(days=6)).isoformat())).fetchall();occupied={r["scheduled_date"] for r in visible};preserved=sum(float(r["distance_km"] or 0) for r in visible);candidates=base._schedule_remaining_slots(ws,remaining,occupied)
    fixed_equivalent=sum(float(equivalent[t[1]]) for _,t in candidates if t[1] in equivalent);variable_candidate=sum(float(t[2]) for _,t in candidates if t[1] not in equivalent);remaining_km=max(0,total-preserved-fixed_equivalent);scale=min(1,remaining_km/variable_candidate) if variable_candidate>0 else 0;generation=datetime.now(timezone.utc).isoformat();basis=plan_basis(c,ws,race,total,phase)
    for scheduled,t in candidates:
        typ,title,km,zone,rpe,purpose,instructions=t;session=take(t);fixed=title in equivalent;effective=float(km) if fixed else float(km)*scale
        if effective<=.05:continue
        low,high=zones.get(zone,(None,None));dose=1 if fixed else effective/max(float(km),.001)
        details={"purpose":purpose,"instructions":instructions,"phase":phase,"week_target_km":round(total,1),"rpe_target":rpe,"plan_basis":basis,"physiological_target":session.target.value if session else None,"variant_key":session.variant_key if session else None,"workout_form":session.display_kind if session else typ,"why":session.why if session else purpose,"load":_scaled_load_dict(session.load,dose) if session else {},"load_model":"planning_estimate_v1","rolling_intensity_distribution":decision.intensity_distribution,"physiological_focus":decision.physiological_focus}
        if session:
            details.update(session.metadata);details["mp_km"]=round(float(session.metadata.get("mp_km",0) or 0)*dose,2)
        if typ=="race":
            if fixed and support_meta:
                details.update({"race_id":support_meta["id"],"race_priority":support_meta["priority"],"goal_seconds":support_meta["goal_seconds"],"replaced_session_km":support_meta["replaced_session_km"],"replaced_session_type":support_meta["replaced_session_type"]})
                if support_meta["priority"]=="B":details["replaced_long_run_km"]=support_meta["replaced_long_run_km"]
            else:details.update({"race_id":int(race["id"]),"race_priority":"A","goal_seconds":int(race["goal_seconds"])})
        c.execute("INSERT INTO workouts(week_start,origin_week_start,scheduled_date,workout_type,title,distance_km,pace_low_s_per_km,pace_high_s_per_km,details_json,status,manual_override,modified_by,generation_version,plan_generation_id) VALUES(?,?,?,?,?,?,?,?,?,'planned',0,'engine',?,?)",(key,key,scheduled.isoformat(),typ,title,round(effective,1),low,high,json.dumps(details,ensure_ascii=False),VERSION,generation))
    if force:set_setting(c,"plan_stale",False);set_setting(c,"plan_stale_reason","")
    return [base._wdict(r) for r in c.execute("SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id",(key,)).fetchall()]


def refresh_plan(c,start:date|None=None,weeks=4):
    requested=base.week_start_for(start or date.today());requested_end=requested+timedelta(days=7*max(0,int(weeks)));safe_start=max(requested,base.week_start_for(date.today()));old=[]
    safe_weeks=max(0,(requested_end-safe_start).days//7)
    if safe_weeks==0:return {"updated":False,"diff":{},"weeks":0,"summary_week_start":safe_start.isoformat(),"past_protected":True}
    for i in range(safe_weeks):
        ws=safe_start+timedelta(days=7*i);rows0=[base._wdict(r) for r in c.execute("SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id",(ws.isoformat(),)).fetchall()]
        if i==0:old=rows0
        generate_week(c,ws,True)
    new=[base._wdict(r) for r in c.execute("SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id",(safe_start.isoformat(),)).fetchall()]
    def stats(xs):return (round(sum(float(x["distance_km"]) for x in xs),1),max([float(x["distance_km"]) for x in xs if x["workout_type"] in {"long","race"}] or [0]),next((x["title"] for x in xs if x["workout_type"]=="quality"),None))
    a,b=stats(old),stats(new);diff={}
    if a[0]!=b[0]:diff["volume_km"]={"old":a[0],"new":b[0]}
    if a[1]!=b[1]:diff["long_run_km"]={"old":a[1],"new":b[1]}
    if a[2]!=b[2]:diff["quality"]={"old":a[2],"new":b[2]}
    if len(old)!=len(new):diff["session_count"]={"old":len(old),"new":len(new)}
    return {"updated":bool(diff),"diff":diff,"weeks":safe_weeks,"summary_week_start":safe_start.isoformat(),"past_protected":True}


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
