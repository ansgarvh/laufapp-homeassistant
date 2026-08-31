from __future__ import annotations

import json
from datetime import date, timedelta

import training as base
import training_planner_v020 as planner
from training_models_v020 import PhysiologicalTarget, TrainingPhase

_APPLIED = False


def apply_runtime_refinements(orchestration) -> None:
    """Patch orchestration/calendar concerns without replacing the planner core."""
    global _APPLIED
    if _APPLIED:
        return

    original_week_sessions = orchestration._week_sessions
    original_weekly_target = orchestration.weekly_target
    original_quality_focus = planner._quality_focus
    original_variation_select = planner.WorkoutVariationEngine.select

    def refined_weekly_target(c, race, ws, readiness):
        total, phase = original_weekly_target(c, race, ws, readiness)
        if phase is TrainingPhase.RACE:
            # Race distance is not optional training volume. Keep only a small
            # amount of pre-race running/frequency around it, but never scale the
            # entered marathon itself down to an artificial taper target.
            established = base.established_volume(c, ws)
            baseline = float(established.get("km") or base._prefs(c, float(race["distance_km"]))["baseline"])
            non_race = max(9.0, min(16.0, baseline * 0.20))
            total = max(float(total), float(race["distance_km"]) + non_race)
        return round(float(total), 1), phase

    def refined_quality_focus(phase, weeks_to_race, hard_long):
        # VO2max has a deliberate but limited place in marathon training. Place
        # it in Build roughly every four weeks, then let it recede in Specific.
        # If the Long Run is already hard/specific, downgrade the other hard day.
        if phase is TrainingPhase.BUILD and weeks_to_race in {10, 14}:
            return PhysiologicalTarget.ECONOMY if hard_long else PhysiologicalTarget.VO2MAX
        return original_quality_focus(phase, weeks_to_race, hard_long)

    def quality_history(c, ws, weeks=6):
        """Return recent quality variants only, newest first.

        The original recency list also contained every Easy and Long-Run variant.
        That diluted the history enough that the exact same quality workout could
        reappear after only four weeks despite many equivalent alternatives.
        """
        rows = c.execute(
            "SELECT scheduled_date,details_json FROM workouts "
            "WHERE workout_type='quality' AND scheduled_date>=? AND scheduled_date<? "
            "ORDER BY scheduled_date DESC,id DESC",
            ((ws - timedelta(days=weeks * 7)).isoformat(), ws.isoformat()),
        ).fetchall()
        out = []
        for row in rows:
            try:
                key = json.loads(row["details_json"] or "{}").get("variant_key")
            except Exception:
                key = None
            if key:
                out.append((str(key), date.fromisoformat(row["scheduled_date"])))
        return out

    def refined_variation_select(self, c, ws, phase, target, dose_scale=1.0):
        selected = original_variation_select(self, c, ws, phase, target, dose_scale)
        recent = quality_history(c, ws, 6)
        last_by_key = {}
        for key, when in recent:
            last_by_key.setdefault(key, when)
        last_selected = last_by_key.get(selected.key)
        if last_selected is None or (ws - last_selected).days >= 35:
            return selected

        # Keep physiological target selection intact. Variation happens only
        # among valid forms for the already chosen target/phase and remains fully
        # deterministic. A repeat is still possible if no equivalent alternative
        # exists, but is heavily penalized for roughly five weeks.
        candidates = [v for v in planner.VARIANTS if v.target is target and phase in v.phase_bias]
        if not candidates:
            candidates = [v for v in planner.VARIANTS if v.target is target]
        if not candidates:
            return selected
        ranked = []
        desired_fatigue = min(1.0, 0.65 * dose_scale)
        for variant in candidates:
            when = last_by_key.get(variant.key)
            gap_days = (ws - when).days if when else 999
            if gap_days < 21:
                repetition_penalty = 180.0
            elif gap_days < 35:
                repetition_penalty = 80.0
            else:
                repetition_penalty = 0.0
            dose_penalty = abs(variant.fatigue_cost - desired_fatigue) * 10.0
            ranked.append(
                (repetition_penalty + dose_penalty, planner._deterministic_tiebreak(ws, variant.key), variant)
            )
        return min(ranked, key=lambda item: (item[0], item[1]))[2]

    def refined_week_sessions(c, race, ws, phase, total):
        dates, sessions, zones, equivalent, b_meta, decision = original_week_sessions(c, race, ws, phase, total)
        dates = list(dates)
        equivalent = dict(equivalent)

        # A-race of any supported distance: use the entered event date (not merely
        # the configured Long-Run weekday) and keep its exact distance. If another
        # planned slot occupies the race date, move that slot to the race session's
        # original date.
        for idx, session in enumerate(sessions):
            if session.workout_type == "race" and session.variant_key in {"race_marathon", "race_target"}:
                race_day = date.fromisoformat(race["race_date"])
                original_date = dates[idx]
                collision = next((i for i, d in enumerate(dates) if i != idx and d == race_day), None)
                if collision is not None:
                    dates[collision] = original_date
                dates[idx] = race_day
                equivalent[session.title] = float(session.distance_km)

            # A history-supported marathon Long Run is a deliberate planner
            # decision. Generic remaining-week scaling must not shrink it back to
            # the old percentage-based value; flexible surrounding sessions absorb
            # the residual budget instead.
            if bool((session.metadata or {}).get("history_supported_share")):
                equivalent[session.title] = float(session.distance_km)

        return dates, sessions, zones, equivalent, b_meta, decision

    planner._quality_focus = refined_quality_focus
    planner.WorkoutVariationEngine.select = refined_variation_select
    orchestration.weekly_target = refined_weekly_target
    orchestration._week_sessions = refined_week_sessions
    _APPLIED = True
