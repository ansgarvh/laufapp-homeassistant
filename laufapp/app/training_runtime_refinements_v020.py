from __future__ import annotations

from datetime import date

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

    def refined_week_sessions(c, race, ws, phase, total):
        dates, sessions, zones, equivalent, b_meta, decision = original_week_sessions(c, race, ws, phase, total)
        dates = list(dates)
        equivalent = dict(equivalent)

        # A-race: use the entered event date (not merely the configured Long-Run
        # weekday) and keep its exact distance. If another planned slot occupies
        # the race date, move that slot to the race session's original date.
        for idx, session in enumerate(sessions):
            if session.variant_key == "race_marathon":
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
    orchestration.weekly_target = refined_weekly_target
    orchestration._week_sessions = refined_week_sessions
    _APPLIED = True
