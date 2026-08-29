from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Literal

from fastapi import HTTPException, Query
from pydantic import BaseModel, Field

import coach as coach_module
import db as db_module
import main as legacy
import training as legacy_training
import training_adaptation_v020 as adaptation_module
import training_v020 as training
from db import db_conn, get_setting, set_setting
from training_adaptation_v020 import (
    adaptation_suggestion,
    coach_context as adaptive_coach_context,
    feedback_for_run,
    recovery_state,
    run_response_metrics,
    save_workout_feedback,
)
from training_guardrails_v020 import enforce_generated_long_run_share
from training_refinements_v020 import apply_training_refinements

APP_VERSION = "0.2.0"
db_module.APP_VERSION = APP_VERSION

# Apply simulator-driven refinements before wiring the planner into the mature
# API surface. The adaptation function is rebound because it was imported above.
apply_training_refinements()
adaptation_suggestion = adaptation_module.adaptation_suggestion

# A mid-week explicit refresh keeps past/completed/manual rows. Re-apply the
# existing long-run-share guardrail only to the newly generated planned Long Run
# so protected user history stays authoritative without allowing the remainder
# of the week to violate the configured cap.
_science_generate_week = training.generate_week
def _guarded_generate_week(c, ws=None, force=False):
    result = _science_generate_week(c, ws, force)
    return enforce_generated_long_run_share(c, result)
training.generate_week = _guarded_generate_week

# Preserve the mature v0.1.9 API/security layer and replace only planner globals.
for _name in ("current_race","generate_week","week_summary","dashboard","automatic_max_weekly_km","refresh_plan"):
    setattr(legacy,_name,getattr(training,_name))
legacy_training.current_race=training.current_race
for _name in ("current_race","generate_week","week_summary"):
    if hasattr(coach_module,_name):setattr(coach_module,_name,getattr(training,_name))

# Coach context is extended, not replaced: the existing race/plan/Health context
# remains present while detailed run response, subjective feedback and readiness
# are added. This also feeds analyze_run without a parallel AI pipeline.
_legacy_coach_context=coach_module.context
def _coach_context_v020(c):
    out=_legacy_coach_context(c);out["adaptive_training"]=adaptive_coach_context(c);return out
coach_module.context=_coach_context_v020

legacy.APP_VERSION=APP_VERSION;legacy.app.version=APP_VERSION;app=legacy.app


class RaceCreate(BaseModel):
    name:str=Field(min_length=1,max_length=120);distance_km:float=Field(gt=1,le=100);race_date:date;goal_seconds:int=Field(gt=300,le=24*3600);priority:Literal["A","B"]="A"
class RaceUpdate(BaseModel):
    name:str=Field(min_length=1,max_length=120);distance_km:float=Field(gt=1,le=100);race_date:date;goal_seconds:int=Field(gt=300,le=24*3600);priority:Literal["A","B"]
class RunShoePayload(BaseModel):shoe_id:int|None=None
class WorkoutFeedbackPayload(BaseModel):
    rpe:int=Field(ge=1,le=10)
    legs:int=Field(ge=1,le=5)
    pain:Literal["none","light","relevant"]="none"
    recovery:int=Field(ge=1,le=5)


def _priority_map(c):
    raw=get_setting(c,"race_priorities",{}) or {};return {str(k):("B" if str(v).upper()=="B" else "A") for k,v in dict(raw).items()}
def _set_priority(c,rid,priority):mapping=_priority_map(c);mapping[str(int(rid))]=priority;set_setting(c,"race_priorities",mapping)
def _remove_priority(c,rid):mapping=_priority_map(c);mapping.pop(str(int(rid)),None);set_setting(c,"race_priorities",mapping)
def _race_week(d):start=legacy.week_start_for(d);return start,start+timedelta(days=6)

def _validate_race_week(c,race_date,exclude_id=None):
    start,end=_race_week(race_date);args=[start.isoformat(),end.isoformat()];sql="SELECT id,name,race_date FROM races WHERE active=1 AND race_date BETWEEN ? AND ?"
    if exclude_id is not None:sql+=" AND id!=?";args.append(int(exclude_id))
    other=c.execute(sql+" ORDER BY race_date,id",tuple(args)).fetchone()
    if other:raise HTTPException(409,f"In dieser Kalenderwoche ist bereits '{other['name']}' eingetragen. Bitte nur ein Rennen pro Trainingswoche planen.")

def _refresh_b_week(c,race_date):
    ws=legacy.week_start_for(race_date)
    if ws+timedelta(days=6)>=date.today():training.generate_week(c,ws,True)

def _race_dict(c,r):
    d=dict(r);d["priority"]=training.race_priority(c,int(r["id"]));p=legacy.predict_distance(c,float(r["distance_km"]));d["recommendation"]={"predicted_seconds":p["predicted_seconds"],"predicted_time":p["predicted_time"],"range_text":p["range_text"],"confidence":p["confidence"]} if p else None;focus=training.current_race(c);d["is_focus"]=bool(focus and int(focus["id"])==int(r["id"]));return d


@app.get("/api/v2/races")
def api_v2_races():
    with db_conn() as c:return [_race_dict(c,r) for r in c.execute("SELECT * FROM races ORDER BY race_date,id").fetchall()]
@app.get("/api/v2/races/recommendation")
def api_v2_race_recommendation(distance_km:float=Query(gt=1,le=100)):
    with db_conn() as c:
        p=legacy.predict_distance(c,distance_km)
        return {"available":False} if not p else {"available":True,"predicted_seconds":p["predicted_seconds"],"predicted_time":p["predicted_time"],"range_text":p["range_text"],"confidence":p["confidence"]}
@app.post("/api/v2/races",status_code=201)
def api_v2_race_add(p:RaceCreate):
    if p.race_date<=date.today():raise HTTPException(400,"Das Wettkampfdatum muss in der Zukunft liegen.")
    with db_conn() as c:
        _validate_race_week(c,p.race_date);cur=c.execute("INSERT INTO races(name,distance_km,race_date,goal_seconds,target_source,active) VALUES(?,?,?,?, 'user',1)",(p.name,p.distance_km,p.race_date.isoformat(),p.goal_seconds));rid=int(cur.lastrowid);_set_priority(c,rid,p.priority)
        if p.priority=="A":legacy.mark_plan_stale(c,"A-Wettkampfplanung geändert")
        else:_refresh_b_week(c,p.race_date)
        return _race_dict(c,c.execute("SELECT * FROM races WHERE id=?",(rid,)).fetchone())
@app.put("/api/v2/races/{rid}")
def api_v2_race_update(rid:int,p:RaceUpdate):
    if p.race_date<=date.today():raise HTTPException(400,"Das Wettkampfdatum muss in der Zukunft liegen.")
    with db_conn() as c:
        old=c.execute("SELECT * FROM races WHERE id=?",(rid,)).fetchone()
        if not old:raise HTTPException(404,"Wettkampf nicht gefunden.")
        old_priority=training.race_priority(c,rid);old_date=date.fromisoformat(old["race_date"]);_validate_race_week(c,p.race_date,rid);c.execute("UPDATE races SET name=?,distance_km=?,race_date=?,goal_seconds=?,target_source='user',active=1 WHERE id=?",(p.name,p.distance_km,p.race_date.isoformat(),p.goal_seconds,rid));_set_priority(c,rid,p.priority)
        if old_priority=="B" and p.priority=="B":
            if old_date!=p.race_date:_refresh_b_week(c,old_date)
            _refresh_b_week(c,p.race_date)
        else:
            if old_priority=="B":_refresh_b_week(c,old_date)
            legacy.mark_plan_stale(c,"A-Wettkampfplanung geändert")
            if p.priority=="B":_refresh_b_week(c,p.race_date)
        return _race_dict(c,c.execute("SELECT * FROM races WHERE id=?",(rid,)).fetchone())
@app.delete("/api/v2/races/{rid}")
def api_v2_race_delete(rid:int):
    with db_conn() as c:
        r=c.execute("SELECT * FROM races WHERE id=?",(rid,)).fetchone()
        if not r:raise HTTPException(404,"Wettkampf nicht gefunden.")
        priority=training.race_priority(c,rid);race_date=date.fromisoformat(r["race_date"]);c.execute("DELETE FROM races WHERE id=?",(rid,));_remove_priority(c,rid)
        if priority=="A":legacy.mark_plan_stale(c,"A-Wettkampfplanung geändert")
        else:_refresh_b_week(c,race_date)
        return {"ok":True}


def _run_with_shoe(c,rid):return c.execute("SELECT r.*,s.brand shoe_brand,s.model shoe_model,s.nickname shoe_nickname FROM runs r LEFT JOIN shoes s ON s.id=r.shoe_id WHERE r.id=?",(rid,)).fetchone()
def _same_day_runs(c,scheduled_date):return c.execute("SELECT * FROM runs WHERE substr(started_at,1,10)=? ORDER BY started_at,id",(scheduled_date,)).fetchall()

@app.get("/api/v2/workouts/{wid}/run-info")
def api_v2_workout_run_info(wid:int):
    with db_conn() as c:
        w=c.execute("SELECT * FROM workouts WHERE id=?",(wid,)).fetchone()
        if not w:raise HTTPException(404,"Training nicht gefunden.")
        run=_run_with_shoe(c,int(w["linked_run_id"])) if w["linked_run_id"] else None;candidates=[] if run else _same_day_runs(c,w["scheduled_date"])
        return {"workout":dict(w),"run":dict(run) if run else None,"single_same_day_candidate":dict(candidates[0]) if len(candidates)==1 else None,"same_day_candidates":len(candidates)}

@app.patch("/api/v2/workouts/{wid}/shoe")
def api_v2_workout_shoe(wid:int,p:RunShoePayload):
    with db_conn() as c:
        w=c.execute("SELECT * FROM workouts WHERE id=?",(wid,)).fetchone()
        if not w:raise HTTPException(404,"Training nicht gefunden.")
        if w["status"]!="completed":raise HTTPException(400,"Ein Schuh kann hier erst nach Abschluss der Einheit zugeordnet werden.")
        run_id=int(w["linked_run_id"]) if w["linked_run_id"] else None
        if run_id is None:
            candidates=_same_day_runs(c,w["scheduled_date"])
            if len(candidates)==1:run_id=int(candidates[0]["id"]);c.execute("UPDATE workouts SET linked_run_id=? WHERE id=?",(run_id,wid))
            elif not candidates:raise HTTPException(400,"Für diese absolvierte Einheit ist noch kein Laufdatensatz vorhanden. Bitte den Lauf zuerst importieren oder manuell eintragen.")
            else:raise HTTPException(409,"An diesem Tag wurden mehrere Läufe gefunden. Bitte den Schuh im Fortschritt-Tab beim konkreten Lauf zuordnen.")
        if p.shoe_id is not None and not c.execute("SELECT id FROM shoes WHERE id=? AND archived=0",(p.shoe_id,)).fetchone():raise HTTPException(400,"Schuh nicht gefunden oder archiviert.")
        c.execute("UPDATE runs SET shoe_id=? WHERE id=?",(p.shoe_id,run_id));run=_run_with_shoe(c,run_id);return {"ok":True,"run":dict(run) if run else None}


@app.get("/api/v2/readiness")
def api_v2_readiness():
    with db_conn() as c:return recovery_state(c).as_dict()

@app.get("/api/v2/runs/{rid}/response")
def api_v2_run_response(rid:int):
    with db_conn() as c:
        try:return run_response_metrics(c,rid)
        except KeyError as e:raise HTTPException(404,str(e))

@app.get("/api/v2/workouts/{wid}/science")
def api_v2_workout_science(wid:int):
    with db_conn() as c:
        w=c.execute("SELECT * FROM workouts WHERE id=?",(wid,)).fetchone()
        if not w:raise HTTPException(404,"Training nicht gefunden.")
        try:details=json.loads(w["details_json"] or "{}")
        except Exception:details={}
        run_id=int(w["linked_run_id"]) if w["linked_run_id"] else None
        return {"workout_id":wid,"status":w["status"],"physiological_target":details.get("physiological_target"),"workout_form":details.get("workout_form"),"why":details.get("why") or details.get("purpose"),"load":details.get("load") or {},"rolling_intensity_distribution":details.get("rolling_intensity_distribution") or {},"training_paces":(details.get("plan_basis") or {}).get("training_paces") or {},"feedback":feedback_for_run(c,run_id) if run_id else None}

@app.post("/api/v2/workouts/{wid}/feedback")
def api_v2_workout_feedback(wid:int,p:WorkoutFeedbackPayload):
    with db_conn() as c:
        try:feedback=save_workout_feedback(c,wid,rpe=p.rpe,legs=p.legs,pain=p.pain,recovery=p.recovery)
        except KeyError as e:raise HTTPException(404,str(e))
        except ValueError as e:raise HTTPException(400,str(e))
        adaptive=adaptation_suggestion(c,date.today());return {"ok":True,"feedback":feedback,**adaptive}

@app.post("/api/v2/adaptation/review")
def api_v2_adaptation_review():
    with db_conn() as c:return adaptation_suggestion(c,date.today())
