from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from typing import Any

import training as base
import training_adaptation_v020 as adaptation
import training_planner_v020 as planner
from db import get_setting
from training_models_v020 import (
    LongRunDecision,
    PhysiologicalTarget,
    PlannedSession,
    ReadinessLevel,
    TrainingPhase,
    WorkoutType,
    WorkoutVariant,
)

_APPLIED = False
_ORIGINAL_LONG_PLAN = planner.LongRunPlanner.plan


EXTRA_VARIANTS: tuple[WorkoutVariant, ...] = (
    WorkoutVariant(
        "aero_progressive_stages",
        PhysiologicalTarget.AEROBIC_PROGRESSION,
        WorkoutType.PROGRESSION,
        "PROGRESSION · 3 kontrollierte Stufen",
        "Locker beginnen, anschließend zwei kontrollierte Steigerungsstufen; die letzte Stufe bleibt klar unter LT2.",
        22,
        "steady",
        0.0,
        "5–6/10",
        (TrainingPhase.FOUNDATION, TrainingPhase.BUILD),
        0.44,
    ),
    WorkoutVariant(
        "mp_3x3k",
        PhysiologicalTarget.MARATHON_SPECIFIC,
        WorkoutType.MARATHON_PACE,
        "MARATHONPACE · 3 × 3 km",
        "2–3 km locker, 3 × 3 km in aktueller Trainings-Marathonpace mit lockeren Zwischenabschnitten, locker auslaufen.",
        0,
        "marathon",
        9.0,
        "6–7/10",
        (TrainingPhase.BUILD, TrainingPhase.SPECIFIC),
        0.64,
    ),
    WorkoutVariant(
        "mp_continuous",
        PhysiologicalTarget.MARATHON_SPECIFIC,
        WorkoutType.MARATHON_PACE,
        "MARATHONPACE · kontrollierter Dauerblock",
        "2–3 km locker, einen zusammenhängenden kontrollierten Block in aktueller Trainings-Marathonpace, locker auslaufen.",
        38,
        "marathon",
        0.0,
        "6–7/10",
        (TrainingPhase.SPECIFIC,),
        0.66,
    ),
    WorkoutVariant(
        "taper_cruise",
        PhysiologicalTarget.THRESHOLD,
        WorkoutType.CRUISE_INTERVALS,
        "SCHWELLE · 3 × 5 min Aktivierung",
        "Locker einlaufen, 3 × 5 min kontrolliert nahe LT2 mit vollständiger lockerer Erholung, locker auslaufen.",
        15,
        "threshold",
        0.0,
        "6/10",
        (TrainingPhase.TAPER,),
        0.34,
    ),
)


def _history_supported_long_plan(self, c, race, ws, phase, total_km, readiness):
    """Relax the share ceiling only when real Long-Run history supports it.

    The former share cap could turn an established 28–30 km marathon runner into
    a 21 km prescription simply because the current week's target was modest.
    Long-run share remains a guardrail, but recent tolerated distance can justify
    a temporary higher share. We still respect the explicit max Long Run, weekly
    volume, phase and readiness, and we never add distance and intensity together.
    """
    decision = _ORIGINAL_LONG_PLAN(self, c, race, ws, phase, total_km, readiness)
    if float(race["distance_km"]) < 40:
        return decision
    if phase not in {TrainingPhase.BUILD, TrainingPhase.SPECIFIC}:
        return decision
    if readiness.level is not ReadinessLevel.GREEN:
        return decision

    actual = base.long_run_history(c, ws)
    longest = max(float(actual.get("longest_4w") or 0), float(actual.get("longest_8w") or 0))
    if longest < 24:
        return decision

    prefs = base._prefs(c, float(race["distance_km"]))
    configured_max = float(prefs["max_long"])
    run_days = max(3, min(7, len(get_setting(c, "training_days", [1, 3, 4, 6]))))
    # Reserve enough room for the other sessions instead of allowing a Long Run
    # to consume the entire week. Four days therefore keep roughly 12 km outside
    # the Long Run; higher frequencies reserve at least 3 km per other session.
    reserve = max(12.0, (run_days - 1) * 3.0)
    feasible_max = max(14.0, float(total_km) - reserve)

    current = float(decision.session.distance_km)
    if decision.primary_progression == "marathon_pace":
        desired = min(configured_max, feasible_max, max(current, longest))
    else:
        desired = min(configured_max, feasible_max, max(current, min(configured_max, longest + 2.5)))
    desired = round(desired, 1)
    if desired <= current + 0.4:
        return decision

    paces = planner.training_paces(c, race)
    previous_mp = float(decision.session.metadata.get("mp_km", 0) or 0)
    if decision.primary_progression == "marathon_pace" and previous_mp > 0:
        mp_km = min(previous_mp, desired * 0.45)
        load = self._load(desired, mp_km, "mp_blocks", paces, 6.5)
        session = replace(
            decision.session,
            title=f"MARATHON-SPECIFIC · {round(desired):g} km inkl. {mp_km:g} km MP",
            distance_km=desired,
            load=load,
            why=(
                decision.session.why
                + f" Deine jüngere Longrun-Historie bis {longest:g} km erlaubt diese Distanz, "
                  "ohne gleichzeitig den Marathonpace-Anteil weiter zu erhöhen."
            ),
            metadata=dict(decision.session.metadata) | {"mp_km": round(mp_km, 1), "history_supported_share": True},
        )
        return LongRunDecision(session, "marathon_pace", longest, decision.previous_mp_km)

    # If history support is what permits the longer run, distance is the sole
    # primary progression. Keep the session easy rather than also progressing
    # pace, Fast Finish or MP content in the same week.
    load = self._load(desired, 0, "easy", paces, 4)
    session = PlannedSession(
        "long",
        f"LONGRUN · {round(desired):g} km Easy",
        desired,
        "easy",
        "3–4/10",
        "Aerobe Ausdauer",
        "Ruhig und gesprächsfähig; Fueling und Trinkstrategie üben.",
        PhysiologicalTarget.AEROBIC_BASE,
        "long_easy",
        WorkoutType.LONG_EASY.value,
        load,
        (
            f"Die jüngere Historie zeigt bereits Longruns bis {longest:g} km. "
            "Deshalb darf der Longrun die normale Anteils-Orientierung vorübergehend überschreiten. "
            "Die Hauptprogression ist ausschließlich die Distanz; die Intensität bleibt bewusst niedrig."
        ),
        {"mp_km": 0, "history_supported_share": True},
    )
    return LongRunDecision(session, "distance", longest, decision.previous_mp_km)


def _refined_adaptation_suggestion(c, ref: date | None = None) -> dict[str, Any]:
    """Create conservative proposals in both directions; never mutate the plan."""
    ref = ref or date.today()
    readiness = adaptation.recovery_state(c, ref)
    workout, _ = adaptation._next_hard_workout(c, ref)
    if not workout:
        return {"readiness": readiness.as_dict(), "suggestion_id": None, "suggestion": None}
    wid = int(workout["id"])
    if adaptation._pending_for_workout(c, wid):
        return {
            "readiness": readiness.as_dict(),
            "suggestion_id": None,
            "suggestion": None,
            "note": "Für diese Einheit ist bereits ein Vorschlag offen.",
        }

    current = float(workout["distance_km"])
    change = title = rationale = None
    if readiness.level is ReadinessLevel.RED:
        proposed = round(max(3, current * 0.62), 1)
        if proposed < current - 0.4:
            change = {"distance_km": proposed}
            title = "Qualitätsreiz deutlich reduzieren"
            rationale = (
                "Mehrere Recovery-Signale sind gemeinsam auffällig. Einzelne HRV-Werte entscheiden nicht isoliert; "
                "die Kombination spricht dafür, den nächsten harten Reiz deutlich zu verkürzen."
            )
    elif readiness.level is ReadinessLevel.YELLOW:
        proposed = round(max(3, current * 0.84), 1)
        if proposed < current - 0.4:
            change = {"distance_km": proposed}
            title = "Qualität leicht reduzieren"
            rationale = (
                "Die Recovery-Lage ist leicht auffällig. Eine kleine Dosisreduktion erhält den Trainingsreiz, "
                "ohne unnötig Ermüdung zu stapeln."
            )
    else:
        feedback = adaptation._recent_feedback(c, ref, 28)
        good = [
            x for x in feedback[-6:]
            if int(x.get("recovery", 3) or 3) >= 4
            and int(x.get("legs", 3) or 3) >= 3
            and str(x.get("pain", "none")) == "none"
            and int(x.get("rpe", 6) or 6) <= 7
        ]
        # The former >=8 km gate accidentally prevented positive adaptation for
        # perfectly valid shorter quality sessions. Four good recent responses
        # are the evidence gate; the progression itself stays deliberately small.
        if len(good) >= 4 and current >= 6:
            increment = min(1.5, current * 0.06) if current >= 8 else min(1.0, max(0.5, current * 0.05))
            proposed = round(current + increment, 1)
            if proposed > current + 0.4:
                change = {"distance_km": proposed}
                title = "Vorsichtige Progression möglich"
                rationale = (
                    "Mehrere Einheiten wurden kontrolliert vertragen und die subjektive Erholung ist stabil. "
                    "Eine kleine Progression ist möglich; schneller laufen ist dabei nicht automatisch das Ziel."
                )

    if not change:
        return {"readiness": readiness.as_dict(), "suggestion_id": None, "suggestion": None}
    payload = {"action": "update_workout", "workout_id": wid, "changes": change}
    cur = c.execute(
        "INSERT INTO suggestions(suggestion_type,title,rationale,payload_json) VALUES('adaptive_plan_change',?,?,?)",
        (title, rationale + " Du entscheidest, ob die Änderung übernommen wird.", json.dumps(payload, ensure_ascii=False)),
    )
    return {
        "readiness": readiness.as_dict(),
        "suggestion_id": int(cur.lastrowid),
        "suggestion": {"title": title, "rationale": rationale, "workout_id": wid, "changes": change},
    }


def apply_training_refinements() -> None:
    global _APPLIED
    if _APPLIED:
        return
    existing = {v.key for v in planner.VARIANTS}
    planner.VARIANTS = planner.VARIANTS + tuple(v for v in EXTRA_VARIANTS if v.key not in existing)
    planner.LongRunPlanner.plan = _history_supported_long_plan
    adaptation.adaptation_suggestion = _refined_adaptation_suggestion
    _APPLIED = True
