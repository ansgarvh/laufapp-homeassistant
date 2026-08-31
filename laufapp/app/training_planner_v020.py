from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from typing import Any

import training as base
from db import get_setting
from training_models_v020 import (
    LongRunDecision, PhysiologicalTarget, PlannedSession, ReadinessLevel,
    RecoveryState, TrainingLoad, TrainingPhase, WeeklyPlanDecision,
    WorkoutType, WorkoutVariant,
)

TARGET_LABELS = {
    PhysiologicalTarget.AEROBIC_BASE: "Aerobe Basis",
    PhysiologicalTarget.THRESHOLD: "Schwelle / LT2",
    PhysiologicalTarget.VO2MAX: "VO₂max",
    PhysiologicalTarget.ECONOMY: "Laufökonomie / Geschwindigkeit",
    PhysiologicalTarget.MARATHON_SPECIFIC: "Marathonspezifische Ausdauer",
    PhysiologicalTarget.AEROBIC_PROGRESSION: "Aerobe Progression",
    PhysiologicalTarget.HILLS: "Hügel / Kraftausdauer",
    PhysiologicalTarget.RECOVERY: "Erholung",
    PhysiologicalTarget.RACE: "Wettkampf",
}

VARIANTS: tuple[WorkoutVariant, ...] = (
    WorkoutVariant("thr_4x2k", PhysiologicalTarget.THRESHOLD, WorkoutType.THRESHOLD_INTERVALS, "SCHWELLE · 4 × 2 km", "2 km locker, 4 × 2 km an kontrollierter Schwelle, 2 min Trabpause, locker auslaufen.", 34, "threshold", 8.0, "7–8/10", (TrainingPhase.BUILD, TrainingPhase.SPECIFIC), 0.78),
    WorkoutVariant("thr_3x3k", PhysiologicalTarget.THRESHOLD, WorkoutType.THRESHOLD_INTERVALS, "SCHWELLE · 3 × 3 km", "2 km locker, 3 × 3 km an kontrollierter Schwelle, 2–3 min Trabpause, locker auslaufen.", 39, "threshold", 9.0, "7–8/10", (TrainingPhase.BUILD, TrainingPhase.SPECIFIC), 0.82),
    WorkoutVariant("thr_2x4k", PhysiologicalTarget.THRESHOLD, WorkoutType.THRESHOLD_INTERVALS, "SCHWELLE · 2 × 4 km", "2 km locker, 2 × 4 km an kontrollierter Schwelle, 3 min Trabpause, locker auslaufen.", 35, "threshold", 8.0, "7–8/10", (TrainingPhase.SPECIFIC,), 0.80),
    WorkoutVariant("thr_3x10", PhysiologicalTarget.THRESHOLD, WorkoutType.CRUISE_INTERVALS, "CRUISE · 3 × 10 min", "2 km locker, 3 × 10 min nahe LT2 mit 2 min Trabpause, locker auslaufen.", 30, "threshold", 0.0, "7/10", (TrainingPhase.FOUNDATION, TrainingPhase.BUILD), 0.62),
    WorkoutVariant("thr_2x15", PhysiologicalTarget.THRESHOLD, WorkoutType.CRUISE_INTERVALS, "SCHWELLE · 2 × 15 min", "2 km locker, 2 × 15 min kontrolliert nahe LT2 mit 3 min Trabpause, locker auslaufen.", 30, "threshold", 0.0, "7/10", (TrainingPhase.BUILD, TrainingPhase.SPECIFIC), 0.66),
    WorkoutVariant("thr_tempo30", PhysiologicalTarget.THRESHOLD, WorkoutType.TEMPO, "TEMPO · 30 min kontrolliert", "2–3 km locker, 25–35 min kontrolliert an der Schwelle, locker auslaufen.", 30, "threshold", 0.0, "7/10", (TrainingPhase.FOUNDATION, TrainingPhase.BUILD, TrainingPhase.SPECIFIC), 0.68),
    WorkoutVariant("thr_progression", PhysiologicalTarget.THRESHOLD, WorkoutType.PROGRESSION, "PROGRESSION · Schwellenfinish", "Locker beginnen und stufenweise steigern; nur der letzte kontrollierte Abschnitt erreicht die Schwelle.", 22, "threshold", 0.0, "6–7/10", (TrainingPhase.FOUNDATION, TrainingPhase.BUILD), 0.55),
    WorkoutVariant("vo2_5x1k", PhysiologicalTarget.VO2MAX, WorkoutType.VO2_INTERVALS, "VO₂MAX · 5 × 1000 m", "2–3 km locker, 5 × 1000 m kontrolliert hochintensiv, vollständige lockere Trabpausen, auslaufen.", 18, "interval", 5.0, "8–9/10", (TrainingPhase.BUILD,), 0.88),
    WorkoutVariant("vo2_6x800", PhysiologicalTarget.VO2MAX, WorkoutType.VO2_INTERVALS, "VO₂MAX · 6 × 800 m", "2–3 km locker, 6 × 800 m kontrolliert hochintensiv, lockere Trabpausen, auslaufen.", 18, "interval", 4.8, "8–9/10", (TrainingPhase.BUILD,), 0.84),
    WorkoutVariant("vo2_5x1200", PhysiologicalTarget.VO2MAX, WorkoutType.VO2_INTERVALS, "VO₂MAX · 4–5 × 1200 m", "2–3 km locker, 4–5 × 1200 m im VO₂max-orientierten Bereich, ausreichend Trabpause, auslaufen.", 22, "interval", 5.4, "8–9/10", (TrainingPhase.BUILD,), 0.92),
    WorkoutVariant("vo2_pyramid", PhysiologicalTarget.VO2MAX, WorkoutType.PYRAMID, "PYRAMIDE · 400–800–1200–1600–1200–800–400 m", "2 km locker, Pyramide kontrolliert VO₂max-orientiert; Pausen so lang, dass die Wiederholungen technisch sauber bleiben; auslaufen.", 23, "interval", 6.4, "8/10", (TrainingPhase.BUILD,), 0.86, True),
    WorkoutVariant("vo2_time_pyramid", PhysiologicalTarget.VO2MAX, WorkoutType.PYRAMID, "PYRAMIDE · 1–2–3–4–3–2–1 min", "2 km locker, 1–2–3–4–3–2–1 min zügig mit lockeren Erholungen; Intensität VO₂max-orientiert, nicht sprinten.", 16, "interval", 0.0, "8/10", (TrainingPhase.FOUNDATION, TrainingPhase.BUILD), 0.72, True),
    WorkoutVariant("economy_10x400", PhysiologicalTarget.ECONOMY, WorkoutType.SHORT_INTERVALS, "SPEED · 10 × 400 m", "2–3 km locker, 10 × 400 m flott aber technisch sauber mit großzügiger Trabpause, locker auslaufen.", 13, "interval", 4.0, "7–8/10", (TrainingPhase.FOUNDATION, TrainingPhase.BUILD, TrainingPhase.TAPER), 0.55),
    WorkoutVariant("economy_fartlek", PhysiologicalTarget.ECONOMY, WorkoutType.FARTLEK, "FARTLEK · kurze schnelle Reize", "Locker laufen und 10–12 kurze kontrollierte schnelle Abschnitte mit vollständiger lockerer Erholung einstreuen.", 12, "interval", 0.0, "6–7/10", (TrainingPhase.FOUNDATION, TrainingPhase.TAPER), 0.42),
    WorkoutVariant("hills_8x90", PhysiologicalTarget.HILLS, WorkoutType.HILLS, "HILLS · 8 × 90 s Berg", "2–3 km locker, 8 × 90 s bergauf kräftig aber kontrolliert, locker zurücktraben, auslaufen.", 12, "threshold", 0.0, "7/10", (TrainingPhase.FOUNDATION, TrainingPhase.BUILD), 0.58),
    WorkoutVariant("hills_10x60", PhysiologicalTarget.HILLS, WorkoutType.HILLS, "HILLS · 10 × 60 s Berg", "2–3 km locker, 10 × 60 s bergauf mit guter Haltung und kontrolliertem Druck, locker zurücktraben, auslaufen.", 10, "threshold", 0.0, "7/10", (TrainingPhase.FOUNDATION, TrainingPhase.BUILD), 0.52),
    WorkoutVariant("aero_progressive", PhysiologicalTarget.AEROBIC_PROGRESSION, WorkoutType.PROGRESSION, "PROGRESSION · 14–18 km", "Überwiegend locker beginnen, im letzten Drittel kontrolliert bis moderat steigern; nicht in einen Schwellentest verwandeln.", 24, "steady", 0.0, "5–6/10", (TrainingPhase.FOUNDATION, TrainingPhase.BUILD), 0.46),
    WorkoutVariant("mp_blocks", PhysiologicalTarget.MARATHON_SPECIFIC, WorkoutType.MARATHON_PACE, "MARATHON-SPECIFIC · MP-Blöcke", "2–3 km locker, mehrere kontrollierte Marathonpace-Blöcke mit lockeren Zwischenabschnitten, locker auslaufen.", 35, "marathon", 0.0, "6–7/10", (TrainingPhase.BUILD, TrainingPhase.SPECIFIC), 0.68),
    WorkoutVariant("taper_threshold", PhysiologicalTarget.THRESHOLD, WorkoutType.CRUISE_INTERVALS, "SCHWELLE · kurze Aktivierung", "Locker einlaufen, 3–4 kurze kontrollierte Schwellenblöcke mit vollständiger Erholung, locker auslaufen.", 14, "threshold", 0.0, "6–7/10", (TrainingPhase.TAPER,), 0.38),
)


def phase_for_week(race, ws: date) -> tuple[TrainingPhase, int]:
    weeks = max(0, (date.fromisoformat(race["race_date"]) - ws).days // 7)
    if weeks == 0: return TrainingPhase.RACE, weeks
    if weeks <= 2: return TrainingPhase.TAPER, weeks
    if weeks <= 8: return TrainingPhase.SPECIFIC, weeks
    if weeks <= 14: return TrainingPhase.BUILD, weeks
    return TrainingPhase.FOUNDATION, weeks


def block_position(race, ws: date, phase: TrainingPhase) -> tuple[int, int]:
    weeks = max(0, (date.fromisoformat(race["race_date"]) - ws).days // 7)
    if phase in {TrainingPhase.FOUNDATION, TrainingPhase.BUILD, TrainingPhase.SPECIFIC}:
        # Race-relative loading sequence: step 1 -> 2 -> 3 -> recovery.
        return (1 - weeks) % 4, 4
    return 0, 0


def training_paces(c, race) -> dict[str, Any]:
    dist = float(race["distance_km"]); goal_pace = float(race["goal_seconds"]) / max(dist, .1)
    marathon_prediction = base.predict_distance(c, 42.195)
    current_mp = float(marathon_prediction["predicted_seconds"]) / 42.195 if marathon_prediction else goal_pace
    # Current fitness caps an over-ambitious goal; a slower goal remains the cap.
    training_mp = max(goal_pace, current_mp)
    p5=base.predict_distance(c,5.0);p10=base.predict_distance(c,10.0);phm=base.predict_distance(c,21.0975)
    threshold = float(phm["predicted_seconds"])/21.0975 if phm else float(p10["predicted_seconds"])/10.0 if p10 else max(180.0,training_mp-18.0)
    interval = float(p5["predicted_seconds"])/5.0 if p5 else max(165.0,threshold-22.0)
    return {
        "goal_marathon_pace_s_per_km":round(goal_pace,1),
        "current_estimated_marathon_pace_s_per_km":round(current_mp,1),
        "training_marathon_pace_s_per_km":round(training_mp,1),
        "marathon_pace_source":"current_estimate" if marathon_prediction and current_mp>=goal_pace else "goal_or_current_cap",
        "easy":(training_mp+55,training_mp+95),"marathon":(training_mp-5,training_mp+5),
        "threshold":(threshold-5,threshold+5),"interval":(interval-4,interval+4),"steady":(training_mp+22,training_mp+45),
    }


def _feedback_values(c,before:date,days:int=21)->list[dict[str,Any]]:
    rows=c.execute("SELECT key,value FROM settings WHERE key LIKE 'workout_feedback:%'").fetchall();out=[];cutoff=before-timedelta(days=days)
    for row in rows:
        try:
            payload=json.loads(row["value"]);d=date.fromisoformat(str(payload.get("date") or payload.get("created_at",""))[:10])
        except Exception:continue
        if cutoff<=d<before:out.append(payload)
    return out


def tolerance_factor(c,before:date)->float:
    feedback=_feedback_values(c,before,35)
    if not feedback:return 1.0
    recent=feedback[-6:]
    good=sum(1 for x in recent if int(x.get("recovery",3) or 3)>=4 and int(x.get("legs",3) or 3)>=3 and str(x.get("pain","none"))=="none" and int(x.get("rpe",6) or 6)<=7)
    bad=sum(1 for x in recent if int(x.get("recovery",3) or 3)<=2 or int(x.get("legs",3) or 3)<=2 or str(x.get("pain","none"))=="relevant" or int(x.get("rpe",6) or 6)>=9)
    if bad>=2:return .90
    if good>=max(3,len(recent)-1):return 1.04
    return 1.0


def weekly_target(c,race,ws:date,readiness:RecoveryState)->tuple[float,TrainingPhase]:
    prefs=base._prefs(c,float(race["distance_km"]));ev=base.established_volume(c,ws);established=float(ev["km"] or prefs["baseline"])
    phase,weeks=phase_for_week(race,ws);pos,cycle=block_position(race,ws,phase);recovery_due=bool(cycle and pos==0 and phase not in {TrainingPhase.TAPER,TrainingPhase.RACE})
    if readiness.level is ReadinessLevel.RED and phase not in {TrainingPhase.TAPER,TrainingPhase.RACE}:recovery_due=True
    step={"gradual":.018,"steady":.028,"progressive":.038}.get(prefs["volume"],.028)*tolerance_factor(c,ws)
    if phase is TrainingPhase.RACE:factor=.40
    elif phase is TrainingPhase.TAPER:factor=.70 if weeks==2 else .50
    elif recovery_due:
        phase=TrainingPhase.RECOVERY;factor=.80 if readiness.level is not ReadinessLevel.RED else .74
    else:
        gain=0 if phase is TrainingPhase.FOUNDATION else .008 if phase is TrainingPhase.BUILD else .012
        factor=1+(step+gain)*max(1,pos)
        if readiness.level is ReadinessLevel.YELLOW:factor=min(factor,.97)
        if ev["trend"]=="reduziert":factor=min(factor,.96)
    recommendation=automatic_max_weekly_km(c,race,ws,readiness)
    user_cap=float(get_setting(c,"max_weekly_km",recommendation)) if get_setting(c,"max_weekly_km_mode","auto")=="user" else recommendation
    return round(max(14.0,min(established*factor,user_cap)),1),phase


def automatic_max_weekly_km(c,race=None,ref:date|None=None,readiness:RecoveryState|None=None)->float:
    race=race or base.current_race(c);dist=float(race["distance_km"]) if race else 42.195;ev=base.established_volume(c,ref)
    established=float(ev["km"] or get_setting(c,"baseline_weekly_km",40.0));active=[v for v in base.weekly_volume(c,6,ref) if v>=5];consistency=len(active)/6
    # Conservative internal ceiling, deliberately not presented as a scientific 10-% rule.
    room=1.06+min(.10,consistency*.08)
    if dist<40:room-=.02
    if ev["trend"]=="reduziert":room*=.95
    if readiness and readiness.level is ReadinessLevel.RED:room=min(room,1.0)
    return round(max(14.0,min(180.0,established*room)),1)


def _recent_variant_keys(c,ws:date,weeks:int=7)->list[str]:
    rows=c.execute("SELECT details_json FROM workouts WHERE scheduled_date>=? AND scheduled_date<? ORDER BY scheduled_date,id",((ws-timedelta(days=weeks*7)).isoformat(),ws.isoformat())).fetchall();keys=[]
    for row in rows:
        try:key=json.loads(row["details_json"] or "{}").get("variant_key")
        except Exception:key=None
        if key:keys.append(str(key))
    return keys


def _deterministic_tiebreak(ws:date,key:str)->int:return int(hashlib.sha1(f"{ws.isoformat()}:{key}".encode()).hexdigest()[:8],16)


class WorkoutVariationEngine:
    def select(self,c,ws:date,phase:TrainingPhase,target:PhysiologicalTarget,dose_scale:float=1.0)->WorkoutVariant:
        candidates=[v for v in VARIANTS if v.target is target and phase in v.phase_bias] or [v for v in VARIANTS if v.target is target] or [v for v in VARIANTS if v.target is PhysiologicalTarget.THRESHOLD]
        recent=_recent_variant_keys(c,ws);ranked=[]
        for v in candidates:
            recency=100 if v.key in recent[-2:] else 35 if v.key in recent[-5:] else 0
            dose=abs(v.fatigue_cost-min(1.0,.65*dose_scale))*10
            ranked.append((recency+dose,_deterministic_tiebreak(ws,v.key),v))
        return min(ranked,key=lambda x:(x[0],x[1]))[2]


def _quality_focus(phase:TrainingPhase,weeks_to_race:int,hard_long:bool)->PhysiologicalTarget:
    block=max(0,weeks_to_race//3)
    if phase is TrainingPhase.FOUNDATION:seq=(PhysiologicalTarget.THRESHOLD,PhysiologicalTarget.HILLS,PhysiologicalTarget.THRESHOLD,PhysiologicalTarget.ECONOMY)
    elif phase is TrainingPhase.BUILD:seq=(PhysiologicalTarget.THRESHOLD,PhysiologicalTarget.VO2MAX,PhysiologicalTarget.THRESHOLD,PhysiologicalTarget.AEROBIC_PROGRESSION)
    elif phase is TrainingPhase.SPECIFIC:seq=(PhysiologicalTarget.MARATHON_SPECIFIC,PhysiologicalTarget.THRESHOLD,PhysiologicalTarget.THRESHOLD,PhysiologicalTarget.VO2MAX)
    elif phase is TrainingPhase.TAPER:return PhysiologicalTarget.ECONOMY if weeks_to_race==1 else PhysiologicalTarget.THRESHOLD
    elif phase is TrainingPhase.RECOVERY:return PhysiologicalTarget.THRESHOLD
    else:return PhysiologicalTarget.RACE
    target=seq[block%len(seq)]
    if hard_long and target in {PhysiologicalTarget.VO2MAX,PhysiologicalTarget.MARATHON_SPECIFIC}:return PhysiologicalTarget.THRESHOLD if phase is TrainingPhase.SPECIFIC else PhysiologicalTarget.ECONOMY
    return target


def _load_score(low:float,moderate:float,high:float,duration:float,rpe:float,long_run:bool=False)->float:
    score=low+1.65*moderate+2.35*high+max(0,rpe-3)*4
    if long_run:score+=duration*.15
    return round(score,1)


def _estimate_quality_session(c,race,phase,target,variant,total_km,hard_long,readiness,dose_scale:float=1.0)->PlannedSession:
    paces=training_paces(c,race);zone=paces.get(variant.intensity_zone,paces["threshold"]);pace_mid=sum(zone)/2
    work_km=variant.work_distance_km or variant.work_minutes*60/max(pace_mid,1);warm_cool=4 if total_km>=45 else 3;distance=work_km+warm_cool
    scale={TrainingPhase.FOUNDATION:.84,TrainingPhase.BUILD:1,TrainingPhase.SPECIFIC:1.08,TrainingPhase.RECOVERY:.62,TrainingPhase.TAPER:.62}.get(phase,1)
    if hard_long:scale*=.72
    scale*=max(.25,min(1.0,float(dose_scale)))
    if readiness.level is ReadinessLevel.YELLOW:scale*=.86
    elif readiness.level is ReadinessLevel.RED:scale*=.65
    distance=max(6,min(total_km*.24,distance*scale));work_min=variant.work_minutes*scale;total_min=distance*sum(paces["easy"])/2/60
    high=work_min if variant.intensity_zone=="interval" else 0;moderate=work_min if variant.intensity_zone in {"threshold","marathon","steady"} else 0;low=max(0,total_min-moderate-high)
    rpe_num=8 if "8" in variant.rpe else 7 if "7" in variant.rpe else 6
    load=TrainingLoad(distance,total_min,variant.intensity_zone,low,moderate,high,moderate+high,moderate if target is PhysiologicalTarget.THRESHOLD else 0,high,moderate if target is PhysiologicalTarget.MARATHON_SPECIFIC else 0,0,0,rpe_num,_load_score(low,moderate,high,total_min,rpe_num))
    why=f"Ziel: {TARGET_LABELS[target]}. Die Trainingsform variiert bewusst, der physiologische Schwerpunkt bleibt blockweise konsistent. "+("Weil der Longrun bereits einen starken Qualitätsreiz enthält, ist die Dosis dieser Einheit bewusst reduziert." if hard_long else "Die Dosis ist an Phase, aktuellen Umfang und Erholung angepasst.")
    return PlannedSession("quality",variant.label,round(distance,1),variant.intensity_zone,variant.rpe,TARGET_LABELS[target],variant.prescription,target,variant.key,variant.workout_type.value,load,why,{"pyramid":variant.pyramid,"work_minutes":round(work_min,1)})


def _long_history(c,ws:date)->list[dict[str,Any]]:
    out=[]
    for row in c.execute("SELECT * FROM workouts WHERE scheduled_date<? AND workout_type IN ('long','race') ORDER BY scheduled_date DESC,id DESC LIMIT 12",(ws.isoformat(),)).fetchall():
        d=dict(row)
        try:d["details"]=json.loads(d.get("details_json") or "{}")
        except Exception:d["details"]={}
        out.append(d)
    return out


def _last_mp_long(history):
    for row in history:
        d=row.get("details") or {}
        if float((d.get("load") or {}).get("marathon_pace_min",0) or 0)>1 or float(d.get("mp_km",0) or 0)>0:return row
    return None


class LongRunPlanner:
    def plan(self,c,race,ws:date,phase:TrainingPhase,total_km:float,readiness:RecoveryState)->LongRunDecision:
        dist=float(race["distance_km"]);prefs=base._prefs(c,dist);paces=training_paces(c,race);history=_long_history(c,ws);actual=base.long_run_history(c,ws)
        previous=history[0] if history else None;previous_distance=float(previous["distance_km"]) if previous else float(actual["longest_4w"] or actual["longest_8w"] or 0);prev_details=previous.get("details",{}) if previous else {};previous_mp=float(prev_details.get("mp_km",0) or 0)
        max_long=min(float(prefs["max_long"]),total_km*min(.47,float(prefs["max_share"])+.03));base_distance=max(14,min(max_long,total_km*(.34 if phase is TrainingPhase.FOUNDATION else .38)))
        if previous_distance>0:base_distance=max(base_distance,min(max_long,previous_distance))
        if phase is TrainingPhase.RACE:
            load=self._load(dist,dist,"race",paces,10)
            label=base.LABELS.get(round(dist,4),f"{dist:g} km")
            return LongRunDecision(PlannedSession("race",f"WETTKAMPF · {label}",dist,"marathon","Wettkampf","Zielwettkampf","Kontrolliert eröffnen und Renntaktik/Verpflegung umsetzen.",PhysiologicalTarget.RACE,"race_target",WorkoutType.RACE.value,load,"Der Zielwettkampf ersetzt den Longrun und ist der zentrale Belastungsreiz der Woche.",{"mp_km":dist if dist>=40 else 0}),"race",previous_distance,previous_mp)
        if dist<40:
            distance=min(max_long,max(9,base_distance));load=self._load(distance,0,"easy",paces,3.5)
            return LongRunDecision(PlannedSession("long","LONGRUN · Easy",round(distance,1),"easy","3–4/10","Aerobe Ausdauer","Ruhig und gesprächsfähig; Verpflegung nach Bedarf üben.",PhysiologicalTarget.AEROBIC_BASE,"long_easy",WorkoutType.LONG_EASY.value,load,"Ziel ist kontinuierliche aerobe Belastung ohne zusätzlichen intensiven Reiz.",{"mp_km":0}),"distance_or_maintenance",previous_distance,previous_mp)
        if phase in {TrainingPhase.RECOVERY,TrainingPhase.TAPER} or readiness.level is ReadinessLevel.RED:
            ratio=.78 if phase is TrainingPhase.RECOVERY else .72 if phase is TrainingPhase.TAPER else .75;distance=min(max_long,max(12,(previous_distance or base_distance)*ratio));load=self._load(distance,0,"easy",paces,3)
            title="LONGRUN · Deload" if phase is TrainingPhase.RECOVERY else "LONGRUN · reduziert";why="Der Longrun wird bewusst gekürzt. Intensität bleibt niedrig, damit Ausdauer erhalten bleibt und gleichzeitig Ermüdung abgebaut werden kann."
            return LongRunDecision(PlannedSession("long",title,round(distance,1),"easy","3/10","Erholung + Ausdauererhalt","Locker laufen; keine forcierte Endbeschleunigung.",PhysiologicalTarget.RECOVERY,"long_deload",WorkoutType.LONG_DELOAD.value,load,why,{"mp_km":0}),"deload",previous_distance,previous_mp)
        weeks_to_race=max(0,(date.fromisoformat(race["race_date"])-ws).days//7);last_mp=_last_mp_long(history);weeks_since_mp=99;last_mp_km=0
        if last_mp:
            weeks_since_mp=max(0,(ws-base.week_start_for(date.fromisoformat(last_mp["scheduled_date"]))).days//7);last_mp_km=float((last_mp.get("details") or {}).get("mp_km",0) or 0)
        eligible=phase in {TrainingPhase.BUILD,TrainingPhase.SPECIFIC} and readiness.level is ReadinessLevel.GREEN
        mp_due=eligible and ((phase is TrainingPhase.BUILD and weeks_to_race<=12 and weeks_since_mp>=3) or (phase is TrainingPhase.SPECIFIC and weeks_since_mp>=2))
        if mp_due and previous_distance>=20:
            distance=min(max_long,max(base_distance,previous_distance or base_distance))
            if previous_distance:distance=min(distance,previous_distance+max(.7,previous_distance*.025))
            floor=4 if phase is TrainingPhase.BUILD else 7;ceiling=min(16,distance*(.30 if phase is TrainingPhase.BUILD else .45));mp_km=round(max(floor,min(ceiling,(last_mp_km+2) if last_mp_km else floor)),1)
            load=self._load(distance,mp_km,"mp_blocks",paces,6.5);blocks="2–3 kontrollierte Blöcke" if mp_km>=8 else "mehrere kurze kontrollierte Blöcke"
            why=f"Heute erhöhen wir primär die Marathonspezifität: {mp_km:g} km liegen ungefähr in der aktuell geschätzten Marathonpace. Die Longrun-Distanz bleibt weitgehend stabil, damit Distanz und Intensität nicht gleichzeitig stark steigen."
            s=PlannedSession("long",f"MARATHON-SPECIFIC · {round(distance):g} km inkl. {mp_km:g} km MP",round(distance,1),"marathon","6–7/10","Marathonspezifische Ermüdungsresistenz",f"Überwiegend locker; {blocks} in Marathonpace. Nicht schneller als die aktuelle Trainings-MP.",PhysiologicalTarget.MARATHON_SPECIFIC,"long_mp_blocks",WorkoutType.LONG_MP_BLOCKS.value,load,why,{"mp_km":mp_km,"weeks_since_mp":weeks_since_mp})
            return LongRunDecision(s,"marathon_pace",previous_distance,previous_mp)
        increment=2 if total_km<65 else 2.5;distance=min(max_long,max(base_distance,(previous_distance+increment) if previous_distance else base_distance))
        if previous_distance and distance>previous_distance+max(3,previous_distance*.10):distance=previous_distance+max(2,previous_distance*.08)
        gain=previous_distance>0 and distance>=previous_distance+1.5
        if gain or phase is TrainingPhase.FOUNDATION or readiness.level is ReadinessLevel.YELLOW:
            kind,share="easy",0;title=f"LONGRUN · {round(distance):g} km Easy";instructions="Ruhig und gesprächsfähig; Fueling und Trinkstrategie üben.";target=PhysiologicalTarget.AEROBIC_BASE;variant="long_easy";display=WorkoutType.LONG_EASY.value;why="Die Hauptprogression ist heute die Distanz. Deshalb bleibt die Intensität bewusst niedrig; so erhöhen wir nicht mehrere Belastungsdimensionen gleichzeitig."
        else:
            kind,share="progression",min(.18,4/max(distance,1));fast=phase is TrainingPhase.SPECIFIC and weeks_to_race%4==3
            if fast:title=f"LONGRUN · {round(distance):g} km Fast Finish";instructions="Überwiegend locker; nur die letzten 15–20 min kontrolliert moderat beschleunigen, klar unter Schwelle und nicht als MP-Test laufen.";variant="long_fast_finish";display=WorkoutType.LONG_FAST_FINISH.value;why="Die Distanz bleibt weitgehend stabil. Ein kurzer Fast-Finish-Reiz trainiert Ermüdungsresistenz, ohne die deutlich größere Belastung eines langen Marathonpace-Blocks zu erzeugen."
            else:title=f"LONGRUN · {round(distance):g} km progressiv";instructions="Überwiegend locker; nur das letzte kurze Segment kontrolliert moderat steigern, nicht bis zur Schwelle.";variant="long_progression";display=WorkoutType.LONG_PROGRESSION.value;why="Die Distanz bleibt weitgehend stabil. Ein kurzer progressiver Schluss setzt einen moderaten Reiz, ohne daraus einen zweiten harten Tempotag zu machen."
            target=PhysiologicalTarget.AEROBIC_PROGRESSION
        load=self._load(distance,0,kind,paces,4 if kind=="easy" else 5,share);s=PlannedSession("long",title,round(distance,1),"easy" if kind=="easy" else "steady","3–4/10" if kind=="easy" else "5/10",TARGET_LABELS[target],instructions,target,variant,display,load,why,{"mp_km":0})
        return LongRunDecision(s,"distance" if gain else "intensity_small",previous_distance,previous_mp)

    @staticmethod
    def _load(distance,mp_km,kind,paces,rpe,moderate_share=0)->TrainingLoad:
        easy=sum(paces["easy"])/2;mp=float(paces["training_marathon_pace_s_per_km"])
        if mp_km>0:mp_min=mp_km*mp/60;low=max(0,(distance-mp_km)*easy/60);moderate=mp_min
        else:duration=distance*easy/60;moderate=duration*moderate_share;low=duration-moderate;mp_min=0
        duration=low+moderate
        return TrainingLoad(distance,duration,kind,low,moderate,0,moderate,0,0,mp_min,0,duration,rpe,_load_score(low,moderate,0,duration,rpe,True))


def easy_session(c,race,distance,index,phase)->PlannedSession:
    paces=training_paces(c,race);duration=distance*sum(paces["easy"])/2/60;strides=phase in {TrainingPhase.FOUNDATION,TrainingPhase.TAPER} and index==0;title="EASY · locker + Strides" if strides else "EASY · Regenerationslauf" if index>0 else "EASY · locker";instructions="Locker und gesprächsfähig. RPE hat Vorrang vor Pace."+(" Am Ende 4–6 kurze lockere Steigerungen mit voller Erholung." if strides else "");high=1.5 if strides else 0;low=max(0,duration-high);load=TrainingLoad(distance,duration,"easy",low,0,high,high,0,high,0,0,0,2.5,_load_score(low,0,high,duration,2.5))
    return PlannedSession("easy",title,round(distance,1),"easy","2–3/10","Aerobe Basis + Erholung",instructions,PhysiologicalTarget.AEROBIC_BASE,"easy_strides" if strides else "easy",WorkoutType.EASY.value,load,"Dieser Lauf liefert niedrigintensives Volumen und schafft Abstand zu den belastenden Reizen der Woche.",{"strides":strides})


def intensity_distribution(sessions):
    low=sum(x.load.low_min for x in sessions);moderate=sum(x.load.moderate_min for x in sessions);high=sum(x.load.high_min for x in sessions);total=low+moderate+high
    return {"low_pct":round(100*low/total,1) if total else 0,"moderate_pct":round(100*moderate/total,1) if total else 0,"high_pct":round(100*high/total,1) if total else 0,"minutes":round(total,1)}


def prior_intensity_minutes(c,ws,weeks=3):
    rows=c.execute("SELECT details_json FROM workouts WHERE scheduled_date>=? AND scheduled_date<? ORDER BY scheduled_date,id",((ws-timedelta(days=weeks*7)).isoformat(),ws.isoformat())).fetchall();sums={"low":0.,"moderate":0.,"high":0.}
    for row in rows:
        try:load=json.loads(row["details_json"] or "{}").get("load") or {}
        except Exception:continue
        for key in sums:sums[key]+=float(load.get(key+"_min",0) or 0)
    return sums


def projected_rolling_distribution(c,ws,sessions):
    prior=prior_intensity_minutes(c,ws,3);low=prior["low"]+sum(x.load.low_min for x in sessions);mod=prior["moderate"]+sum(x.load.moderate_min for x in sessions);high=prior["high"]+sum(x.load.high_min for x in sessions);total=low+mod+high
    return {"low_pct":round(100*low/total,1) if total else 0,"moderate_pct":round(100*mod/total,1) if total else 0,"high_pct":round(100*high/total,1) if total else 0,"weeks":4}


def build_week_sessions(c,race,ws,total_km,phase,readiness)->WeeklyPlanDecision:
    run_days=max(3,min(7,len(get_setting(c,"training_days",[1,3,4,6]))));long_decision=LongRunPlanner().plan(c,race,ws,phase,total_km,readiness);hard_long=long_decision.session.target in {PhysiologicalTarget.MARATHON_SPECIFIC,PhysiologicalTarget.AEROBIC_PROGRESSION};weeks=max(0,(date.fromisoformat(race["race_date"])-ws).days//7)
    if phase is TrainingPhase.RACE:
        easy_count=max(1,run_days-2);remaining=max(6,total_km-float(race["distance_km"])-5);easies=[easy_session(c,race,max(3,remaining/easy_count),i,phase) for i in range(easy_count)]
        load=TrainingLoad(5,28,"marathon",20,8,0,8,0,0,8,0,0,5,_load_score(20,8,0,28,5));activation=PlannedSession("raceprep","RACE PREP · kurze MP-Aktivierung",5,"marathon","5/10","Aktivierung ohne Ermüdung","Locker einlaufen, wenige kurze Abschnitte in aktueller Marathonpace, früh beenden.",PhysiologicalTarget.MARATHON_SPECIFIC,"raceprep",WorkoutType.RACE_PREP.value,load,"Kurze Intensität bleibt erhalten, während das Volumen stark reduziert ist.",{})
        sessions=easies+[activation,long_decision.session];return WeeklyPlanDecision(tuple(sessions),phase,readiness,projected_rolling_distribution(c,ws,sessions),"Wettkampf + Frische")
    configured=max(1,min(3,int(get_setting(c,"quality_sessions_per_week",2))));variation=WorkoutVariationEngine();target=_quality_focus(phase,weeks,hard_long)
    single_quality_consumed_by_long=hard_long and configured<=1
    if single_quality_consumed_by_long:
        # The configured single hard stimulus is already the Long Run. Keep the
        # other structured day as a small neuromuscular/economy activation, not
        # a second threshold/VO2 session disguised as "reduced" quality.
        target=PhysiologicalTarget.ECONOMY
    dose=.45 if single_quality_consumed_by_long else .65 if hard_long else 1
    if phase in {TrainingPhase.RECOVERY,TrainingPhase.TAPER}:dose*=.65
    variant=variation.select(c,ws,phase if phase is not TrainingPhase.RECOVERY else TrainingPhase.TAPER,target,dose);quality=_estimate_quality_session(c,race,phase,target,variant,total_km,hard_long,readiness,.55 if single_quality_consumed_by_long else 1.0)
    quality_slots=2 if run_days>=6 and configured>=2 and not hard_long and readiness.level is ReadinessLevel.GREEN and phase in {TrainingPhase.BUILD,TrainingPhase.SPECIFIC} else 1;qualities=[quality]
    if quality_slots==2:
        secondary=PhysiologicalTarget.ECONOMY if target is not PhysiologicalTarget.ECONOMY else PhysiologicalTarget.THRESHOLD;v2=variation.select(c,ws+timedelta(days=1),phase,secondary,.58);qualities.append(_estimate_quality_session(c,race,phase,secondary,v2,total_km,False,readiness))
    used=sum(x.distance_km for x in qualities)+long_decision.session.distance_km;easy_slots=max(1,run_days-len(qualities)-1);easy_km=max(3,(total_km-used)/easy_slots);easies=[easy_session(c,race,easy_km,i,phase) for i in range(easy_slots)]
    sessions=[easies[0],qualities[0],*easies[1:],long_decision.session] if len(qualities)==1 else [easies[0],qualities[0]]+([easies[1]] if len(easies)>1 else [])+[qualities[1]]+easies[2:]+[long_decision.session]
    excess=sum(x.distance_km for x in sessions)-total_km
    if excess>.4:
        for idx in reversed([i for i,x in enumerate(sessions) if x.workout_type=="easy"]):
            if excess<=0:break
            x=sessions[idx];cut=min(max(0,x.distance_km-3),excess)
            if cut>0:sessions[idx]=easy_session(c,race,x.distance_km-cut,idx,phase);excess-=cut
    rolling=projected_rolling_distribution(c,ws,sessions)
    if rolling["low_pct"]<70 and readiness.level is not ReadinessLevel.GREEN:
        for i,x in enumerate(sessions):
            if x.workout_type=="quality":sessions[i]=_estimate_quality_session(c,race,phase,target,variant,total_km,hard_long,RecoveryState(ReadinessLevel.RED,readiness.score,readiness.reasons,readiness.signals),.55 if single_quality_consumed_by_long else 1.0);break
        rolling=projected_rolling_distribution(c,ws,sessions)
    return WeeklyPlanDecision(tuple(sessions),phase,readiness,rolling,TARGET_LABELS.get(target,target.value))