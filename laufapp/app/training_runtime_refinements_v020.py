from __future__ import annotations

from datetime import date

import training as base
from training_models_v020 import TrainingPhase

_APPLIED = False


def apply_runtime_refinements(orchestration) -> None:
    """Patch only orchestration concerns that cannot live in the physiology layer.

    The scientific planner decides the session. The orchestration layer decides
    calendar placement and protects fixed event/session distances from generic
    residual-week scaling.
    """
    global _APPLIED
    if _APPLIED:
        return

    original_week_sessions = orchestration._week_sessions
    original_weekly_target = orchestration.weekly_target

    def refined_weekly_target(c, race, ws, readiness):
        total, phase = original_weekly_target(c, race, ws, readiness)
        if phase is TrainingPhase.RACE:
            # Race distance is not optional training volume. Keep a small amount
            # of pre-race running/frequency while never scaling the marathon down
            # merely because the taper target is lower than 42.195 km.
            established = base.established_volume(c, ws)
            baseline = float(established.get("km") or base._prefs(c, float(race["distance_km"]))["baseline"])
            non_race = max(9.0, min(16.0, baseline * 0.20))
            total = max(float(total), float(race["distance_km"]) + non_race)
        return round(float(total), 1), phase

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

    orchestration.weekly_target = refined_weekly_target
    orchestration._week_sessions = refined_week_sessions
    _APPLIED = True
