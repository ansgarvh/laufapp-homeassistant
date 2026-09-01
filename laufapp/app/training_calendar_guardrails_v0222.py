"""Calendar-order and key-session spacing guardrails for Laufapp v0.2.22.

The planner stores dates, not workout start times.  The requested 48-hour
buffer is therefore represented as at least two calendar days between key
sessions.  Only untouched future engine sessions may be rearranged.  Races,
Long Runs and every user-owned/completed/skipped/linked row remain fixed.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from itertools import permutations
from math import isfinite
from typing import Any

import training as base


MIN_KEY_SESSION_GAP_DAYS = 2
VERY_LONG_RUN_MIN_KM = 24.0
VERY_LONG_RUN_MIN_DURATION_MIN = 120.0
_MOVABLE_WORKOUT_TYPES = {"easy", "quality", "raceprep"}
_STRUCTURED_WORKOUT_TYPES = {"quality", "raceprep", "race"}
_SPECIFIC_LONG_TARGETS = {"marathon_specific", "aerobic_progression"}
_SPECIFIC_LONG_FORMS = {"long_mp_blocks", "long_fast_finish", "long_progression"}


def _details(workout: dict[str, Any]) -> dict[str, Any]:
    value = workout.get("details")
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(workout.get("details_json") or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _finite_float(value: Any) -> float:
    try:
        parsed = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return parsed if isfinite(parsed) else 0.0


def _has_manual_override(workout: dict[str, Any]) -> bool:
    try:
        return int(workout.get("manual_override") or 0) != 0
    except (TypeError, ValueError):
        # Treat malformed legacy ownership markers conservatively as protected.
        return True


def _workout_date(workout: dict[str, Any]) -> date | None:
    try:
        return date.fromisoformat(str(workout.get("scheduled_date") or ""))
    except ValueError:
        return None


def _is_active(workout: dict[str, Any]) -> bool:
    """Skipped sessions are not training loads for calendar-spacing checks."""
    return str(workout.get("status") or "planned") != "skipped"


def is_key_session(workout: dict[str, Any]) -> bool:
    """Classify quality/race loads and long or specific Long Runs."""
    if not _is_active(workout):
        return False
    workout_type = str(workout.get("workout_type") or "")
    if workout_type in _STRUCTURED_WORKOUT_TYPES:
        return True
    if workout_type != "long":
        return False

    details = _details(workout)
    load = details.get("load") if isinstance(details.get("load"), dict) else {}
    duration = _finite_float(
        load.get("long_run_duration_min")
        or load.get("duration_min")
        or 0
    )
    distance = _finite_float(workout.get("distance_km"))
    target = str(details.get("physiological_target") or "")
    form = str(details.get("workout_form") or details.get("variant_key") or "")
    mp_km = _finite_float(details.get("mp_km"))
    return (
        distance >= VERY_LONG_RUN_MIN_KM
        or duration >= VERY_LONG_RUN_MIN_DURATION_MIN
        or target in _SPECIFIC_LONG_TARGETS
        or form in _SPECIFIC_LONG_FORMS
        or mp_km > 0.05
    )


def _is_protected(workout: dict[str, Any], today: date) -> bool:
    scheduled = _workout_date(workout)
    return (
        str(workout.get("status") or "planned") != "planned"
        or workout.get("linked_run_id") is not None
        or _has_manual_override(workout)
        or str(workout.get("modified_by") or "engine") != "engine"
        or scheduled is None
        or scheduled < today
    )


def _is_movable(workout: dict[str, Any], today: date) -> bool:
    return (
        str(workout.get("workout_type") or "") in _MOVABLE_WORKOUT_TYPES
        and not _is_protected(workout, today)
    )


def _key_gap_violations(
    workouts: list[dict[str, Any]],
    relevant_ids: set[int] | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any], int]]:
    keys = [w for w in workouts if is_key_session(w) and _workout_date(w) is not None]
    out = []
    for index, first in enumerate(keys):
        for second in keys[index + 1:]:
            first_id = int(first.get("id") or 0)
            second_id = int(second.get("id") or 0)
            if relevant_ids is not None and first_id not in relevant_ids and second_id not in relevant_ids:
                continue
            gap = abs((_workout_date(second) - _workout_date(first)).days)
            if gap < MIN_KEY_SESSION_GAP_DAYS:
                out.append((first, second, gap))
    return out


def _quality_after_easy_violations(
    workouts: list[dict[str, Any]],
    relevant_ids: set[int] | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    active = [w for w in workouts if _is_active(w) and _workout_date(w) is not None]
    out = []
    for easy in active:
        if str(easy.get("workout_type") or "") != "easy":
            continue
        for quality in active:
            if str(quality.get("workout_type") or "") != "quality":
                continue
            easy_id = int(easy.get("id") or 0)
            quality_id = int(quality.get("id") or 0)
            if relevant_ids is not None and easy_id not in relevant_ids and quality_id not in relevant_ids:
                continue
            if (_workout_date(quality) - _workout_date(easy)).days == 1:
                out.append((easy, quality))
    return out


def _external_rows(c, current: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dated = [_workout_date(w) for w in current]
    dated = [d for d in dated if d is not None]
    if not dated:
        return []
    start = min(dated) - timedelta(days=1)
    end = max(dated) + timedelta(days=1)
    current_ids = {int(w.get("id") or 0) for w in current}
    return [
        dict(row)
        for row in c.execute(
            "SELECT * FROM workouts WHERE scheduled_date BETWEEN ? AND ? ORDER BY scheduled_date,id",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        if int(row["id"]) not in current_ids
    ]


def _score(
    current: list[dict[str, Any]],
    external: list[dict[str, Any]],
    original_dates: dict[int, date],
) -> tuple[int, int, int]:
    combined = current + external
    key_shortfall = sum(
        MIN_KEY_SESSION_GAP_DAYS - gap
        for _, _, gap in _key_gap_violations(combined)
    )
    wrong_order = len(_quality_after_easy_violations(combined))
    displacement = sum(
        abs((_workout_date(w) - original_dates[int(w["id"])]).days)
        for w in current
        if int(w.get("id") or 0) in original_dates and _workout_date(w) is not None
    )
    return key_shortfall, wrong_order, displacement


def _apply_date_changes(c, assignments: dict[int, date]) -> None:
    if not assignments:
        return
    # A fixed temporary assignment table keeps the multi-row date permutation
    # atomic without constructing SQL identifiers or value placeholders.
    c.execute(
        "CREATE TEMP TABLE IF NOT EXISTS calendar_guardrail_assignments("
        "workout_id INTEGER PRIMARY KEY,scheduled_date TEXT NOT NULL)"
    )
    c.execute("DELETE FROM calendar_guardrail_assignments")
    c.executemany(
        "INSERT INTO calendar_guardrail_assignments(workout_id,scheduled_date) VALUES(?,?)",
        [
            (workout_id, scheduled.isoformat())
            for workout_id, scheduled in sorted(assignments.items())
        ],
    )
    c.execute(
        "UPDATE workouts SET scheduled_date=(SELECT scheduled_date FROM calendar_guardrail_assignments "
        "WHERE workout_id=workouts.id) WHERE id IN "
        "(SELECT workout_id FROM calendar_guardrail_assignments)"
    )
    c.execute("DELETE FROM calendar_guardrail_assignments")


def _rows_for_ids(c, ids: list[int]) -> list[Any]:
    rows = []
    for workout_id in ids:
        row = c.execute("SELECT * FROM workouts WHERE id=?", (workout_id,)).fetchone()
        if row is not None:
            rows.append(row)
    return sorted(rows, key=lambda row: (str(row["scheduled_date"]), int(row["id"])))


def _optimise_group(c, current: list[dict[str, Any]], today: date) -> None:
    movable = [w for w in current if _is_movable(w, today)]
    if len(movable) < 2:
        return
    slots = sorted(_workout_date(w) for w in movable)
    if any(slot is None for slot in slots) or len(set(slots)) != len(slots):
        return

    movable = sorted(movable, key=lambda w: (_workout_date(w), int(w["id"])))
    original_dates = {int(w["id"]): _workout_date(w) for w in movable}
    fixed = [w for w in current if int(w["id"]) not in original_dates]
    external = _external_rows(c, current)
    best_rows = current
    best_key = _score(current, external, original_dates) + (
        tuple(int(w["id"]) for w in movable),
    )

    for ordered_sessions in permutations(movable):
        assigned = []
        for workout, slot in zip(ordered_sessions, slots):
            assigned.append(dict(workout) | {"scheduled_date": slot.isoformat()})
        candidate = fixed + assigned
        candidate_key = _score(candidate, external, original_dates) + (
            tuple(int(w["id"]) for w in ordered_sessions),
        )
        if candidate_key < best_key:
            best_key = candidate_key
            best_rows = candidate

    assignments = {
        int(w["id"]): _workout_date(w)
        for w in best_rows
        if int(w.get("id") or 0) in original_dates
        and _workout_date(w) != original_dates[int(w["id"])]
    }
    _apply_date_changes(c, assignments)


def enforce_calendar_rules(c, workouts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reorder only safe engine slots and return the refreshed public rows."""
    ids = sorted({int(w.get("id") or 0) for w in workouts if int(w.get("id") or 0) > 0})
    if not ids:
        return workouts
    rows = [dict(row) for row in _rows_for_ids(c, ids)]
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row.get("week_start") or ""), []).append(row)
    today = date.today()
    for group in groups.values():
        _optimise_group(c, group, today)
    return [base._wdict(row) for row in _rows_for_ids(c, ids)]


def calendar_rule_report(c, workouts: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe remaining conflicts after safe automatic optimisation."""
    current = [dict(w) for w in workouts]
    current_ids = {int(w.get("id") or 0) for w in current}
    combined = current + _external_rows(c, current)
    key_pairs = _key_gap_violations(combined, current_ids)
    ordering_pairs = _quality_after_easy_violations(combined, current_ids)

    key_workouts = [
        w for w in combined if is_key_session(w) and _workout_date(w) is not None
    ]
    observed = [
        abs((_workout_date(second) - _workout_date(first)).days) * 24
        for index, first in enumerate(key_workouts)
        for second in key_workouts[index + 1:]
        if int(first.get("id") or 0) in current_ids
        or int(second.get("id") or 0) in current_ids
    ]
    alerts = []
    for first, second, gap in key_pairs:
        alerts.append({
            "level": "warn",
            "text": (
                f"Zwischen „{first.get('title') or 'Schlüsselbelastung'}“ und "
                f"„{second.get('title') or 'Schlüsselbelastung'}“ liegt nur "
                f"{gap * 24} h kalenderbasiert. Mindestens 48 h konnten wegen "
                "fester oder geschützter Termine nicht automatisch hergestellt werden."
            ),
        })
    for easy, quality in ordering_pairs:
        alerts.append({
            "level": "info",
            "text": (
                f"„{easy.get('title') or 'Easy Run'}“ liegt unmittelbar vor "
                f"„{quality.get('title') or 'Qualitätseinheit'}“. Die bevorzugte "
                "Reihenfolge Qualität → Easy konnte wegen fester oder geschützter "
                "Termine nicht automatisch hergestellt werden."
            ),
        })
    return {
        "minimum_key_session_gap_hours": MIN_KEY_SESSION_GAP_DAYS * 24,
        "minimum_observed_key_session_gap_hours": min(observed) if observed else None,
        "key_session_spacing_ok": not key_pairs,
        "quality_before_easy_ok": not ordering_pairs,
        "date_based": True,
        "alerts": alerts,
    }
