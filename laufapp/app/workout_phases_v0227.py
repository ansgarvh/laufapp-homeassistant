"""Structured workout phases for Laufapp v0.2.27.

The established planner stores a compact workout row plus explanatory metadata.
This module turns that existing information into a stable, structured phase
contract without migrating or rewriting persistent workout rows.  Consequently
already planned, completed, skipped and manually moved sessions remain intact.
"""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any


PHASE_SCHEMA_VERSION = 1


_VARIANT_SPECS: dict[str, dict[str, Any]] = {
    "thr_4x2k": {"mode": "distance_repeats", "repetitions": 4, "repeat_km": 2.0, "recovery_repetitions": 3, "recovery_s": 120},
    "thr_3x3k": {"mode": "distance_repeats", "repetitions": 3, "repeat_km": 3.0, "recovery_repetitions": 2, "recovery_min_s": 120, "recovery_max_s": 180},
    "thr_2x4k": {"mode": "distance_repeats", "repetitions": 2, "repeat_km": 4.0, "recovery_repetitions": 1, "recovery_s": 180},
    "thr_3x10": {"mode": "time_repeats", "repetitions": 3, "repeat_s": 600, "recovery_repetitions": 2, "recovery_s": 120},
    "thr_2x15": {"mode": "time_repeats", "repetitions": 2, "repeat_s": 900, "recovery_repetitions": 1, "recovery_s": 180},
    "thr_tempo30": {"mode": "continuous"},
    "thr_progression": {"mode": "progression", "stages": 3},
    "vo2_5x1k": {"mode": "distance_repeats", "repetitions": 5, "repeat_km": 1.0, "recovery_repetitions": 4, "recovery_min_s": 120, "recovery_max_s": 180},
    "vo2_6x800": {"mode": "distance_repeats", "repetitions": 6, "repeat_km": 0.8, "recovery_repetitions": 5, "recovery_min_s": 90, "recovery_max_s": 150},
    "vo2_5x1200": {"mode": "distance_repeat_range", "repetitions_min": 4, "repetitions_max": 5, "repeat_km": 1.2, "recovery_repetitions_min": 3, "recovery_repetitions_max": 4, "recovery_min_s": 120, "recovery_max_s": 180},
    "vo2_pyramid": {"mode": "structure", "structure": "400–800–1200–1600–1200–800–400 m", "recovery": "vollständige lockere Erholung"},
    "vo2_time_pyramid": {"mode": "structure", "structure": "1–2–3–4–3–2–1 min", "recovery": "lockere Erholung zwischen den Stufen"},
    "economy_10x400": {"mode": "distance_repeats", "repetitions": 10, "repeat_km": 0.4, "recovery_repetitions": 9, "recovery_min_s": 90, "recovery_max_s": 120},
    "economy_fartlek": {"mode": "repetition_range", "repetitions_min": 10, "repetitions_max": 12, "structure": "kurze kontrollierte Reize", "recovery": "vollständige lockere Erholung"},
    "hills_8x90": {"mode": "time_repeats", "repetitions": 8, "repeat_s": 90, "recovery_repetitions": 7, "recovery": "locker zurücktraben"},
    "hills_10x60": {"mode": "time_repeats", "repetitions": 10, "repeat_s": 60, "recovery_repetitions": 9, "recovery": "locker zurücktraben"},
    "aero_progressive": {"mode": "progression", "stages": 3},
    "aero_progressive_stages": {"mode": "progression", "stages": 3},
    "mp_blocks": {"mode": "mp_blocks", "recovery": "lockerer Zwischenabschnitt"},
    "mp_3x3k": {"mode": "distance_repeats", "repetitions": 3, "repeat_km": 3.0, "recovery_repetitions": 2, "recovery": "lockerer Zwischenabschnitt"},
    "mp_continuous": {"mode": "continuous"},
    "taper_threshold": {"mode": "time_repeat_range", "repetitions_min": 3, "repetitions_max": 4, "recovery": "vollständige lockere Erholung"},
    "taper_cruise": {"mode": "time_repeats", "repetitions": 3, "repeat_s": 300, "recovery_repetitions": 2, "recovery": "vollständige lockere Erholung"},
    "raceprep": {"mode": "repetition_range", "repetitions_min": 3, "repetitions_max": 4, "structure": "kurze Marathonpace-Abschnitte", "recovery": "vollständige lockere Erholung"},
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _km(value: Any) -> float:
    return round(max(0.0, _number(value)), 2)


def _pace_text(low: float | None, high: float | None) -> str | None:
    if not low or not high or low <= 0 or high <= 0:
        return None

    def one(value: float) -> str:
        seconds = max(1, int(round(value)))
        minutes, remainder = divmod(seconds, 60)
        return f"{minutes}:{remainder:02d}"

    return f"{one(low)}–{one(high)}/km"


def _de_number(value: float, digits: int = 1) -> str:
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _seconds_target(seconds: int) -> str:
    if seconds % 60 == 0:
        return f"{seconds // 60} min"
    return f"{seconds} s"


def _duration_range_target(minimum: int, maximum: int) -> str:
    if minimum == maximum:
        return _seconds_target(minimum)
    if minimum % 60 == 0 and maximum % 60 == 0:
        return f"{minimum // 60}–{maximum // 60} min"
    return f"{_seconds_target(minimum)}–{_seconds_target(maximum)}"


def _phase(
    kind: str,
    label: str,
    target_text: str,
    instruction: str,
    pace: tuple[float | None, float | None] = (None, None),
    **values: Any,
) -> dict[str, Any]:
    low, high = pace
    result: dict[str, Any] = {
        "kind": kind,
        "label": label,
        "target_text": target_text,
        "instruction": instruction,
        "pace_low_s_per_km": round(low, 1) if low else None,
        "pace_high_s_per_km": round(high, 1) if high else None,
        "pace_text": _pace_text(low, high),
    }
    result.update(values)
    return result


def _details(workout: dict[str, Any]) -> dict[str, Any]:
    raw = workout.get("details")
    return deepcopy(raw) if isinstance(raw, dict) else {}


def _stored_pace(workout: dict[str, Any]) -> tuple[float | None, float | None]:
    low = _number(workout.get("pace_low_s_per_km"))
    high = _number(workout.get("pace_high_s_per_km"))
    return (low or None, high or None)


def _training_marathon_pace(details: dict[str, Any]) -> float | None:
    basis = details.get("plan_basis")
    paces = basis.get("training_paces") if isinstance(basis, dict) else None
    if not isinstance(paces, dict):
        return None
    value = _number(
        paces.get("training_marathon_pace_s_per_km")
        or paces.get("current_estimated_marathon_pace_s_per_km")
        or paces.get("goal_marathon_pace_s_per_km")
    )
    return value or None


def _easy_pace(workout: dict[str, Any], details: dict[str, Any]) -> tuple[float | None, float | None]:
    if workout.get("workout_type") == "easy":
        return _stored_pace(workout)
    variant = str(details.get("variant_key") or "")
    if workout.get("workout_type") == "long" and variant in {"long_easy", "long_deload"}:
        return _stored_pace(workout)
    marathon = _training_marathon_pace(details)
    return (marathon + 55, marathon + 95) if marathon else (None, None)


def _steady_pace(details: dict[str, Any]) -> tuple[float | None, float | None]:
    marathon = _training_marathon_pace(details)
    return (marathon + 22, marathon + 45) if marathon else (None, None)


def _warm_and_cool(total_km: float, work_km: float | None = None) -> tuple[float, float, float]:
    if work_km is not None:
        work = min(max(0.5, work_km), max(0.5, total_km - 2.5))
        remainder = max(0.0, total_km - work)
        warm = min(3.0, max(1.5, remainder / 2))
        cool = max(1.0, remainder - warm)
        return _km(warm), _km(work), _km(cool)
    warm = 2.5 if total_km >= 13 else 2.0 if total_km >= 8 else 1.5
    cool = 2.0 if total_km >= 8 else 1.0
    if warm + cool > total_km - 1:
        warm = max(1.0, total_km * 0.25)
        cool = max(0.8, total_km * 0.2)
    return _km(warm), _km(max(0.5, total_km - warm - cool)), _km(cool)


def _recovery_phase(spec: dict[str, Any], easy_pace: tuple[float | None, float | None]) -> dict[str, Any] | None:
    repetitions = spec.get("recovery_repetitions")
    repetitions_min = spec.get("recovery_repetitions_min")
    repetitions_max = spec.get("recovery_repetitions_max")
    exact = int(spec.get("recovery_s") or 0)
    minimum = int(spec.get("recovery_min_s") or 0)
    maximum = int(spec.get("recovery_max_s") or 0)
    text = str(spec.get("recovery") or "").strip()
    if exact:
        value = _seconds_target(exact)
    elif minimum and maximum:
        value = _duration_range_target(minimum, maximum)
    elif text:
        value = text
    else:
        return None
    prefix = ""
    if repetitions:
        prefix = f"{int(repetitions)} × "
    elif repetitions_min and repetitions_max:
        prefix = f"{int(repetitions_min)}–{int(repetitions_max)} × "
    return _phase(
        "recovery",
        "Erholung zwischen Wiederholungen",
        prefix + value,
        text or "Sehr locker traben; die nächste Wiederholung technisch sauber beginnen.",
        easy_pace,
        repetitions=int(repetitions) if repetitions else None,
        repetitions_min=int(repetitions_min) if repetitions_min else None,
        repetitions_max=int(repetitions_max) if repetitions_max else None,
        duration_s=exact or None,
        duration_min_s=minimum or None,
        duration_max_s=maximum or None,
        counted_in_distance=False,
    )


def _work_instruction(details: dict[str, Any]) -> str:
    target = str(details.get("physiological_target") or "")
    if target == "marathon_specific":
        return "Aktuelle Trainings-Marathonpace gleichmäßig halten; nicht schneller werden."
    if target == "threshold":
        return "Kontrolliert nahe der Schwelle laufen; der Zielbereich ist eine Obergrenze, kein Test."
    if target == "vo2max":
        return "Kontrolliert hochintensiv laufen, technisch sauber bleiben und nicht sprinten."
    if target == "hills":
        return "Bergauf kräftig, aber kontrolliert mit stabiler Haltung laufen."
    if target in {"economy", "aerobic_progression"}:
        return "Kontrolliert steigern und sauber laufen; nicht bis zum All-out-Bereich beschleunigen."
    return "Den vorgegebenen Zielbereich kontrolliert und gleichmäßig laufen."


def _quality_phases(workout: dict[str, Any], details: dict[str, Any]) -> list[dict[str, Any]]:
    total = max(0.1, _number(workout.get("distance_km"), 0.1))
    variant = str(details.get("variant_key") or "")
    spec = _VARIANT_SPECS.get(variant, {"mode": "continuous"})
    mode = str(spec.get("mode") or "continuous")
    easy = _easy_pace(workout, details)
    work_pace = _stored_pace(workout)
    nominal_work = None
    if mode == "distance_repeats":
        nominal_work = _number(spec.get("repetitions")) * _number(spec.get("repeat_km"))
    elif mode == "distance_repeat_range":
        nominal_work = _number(spec.get("repetitions_min")) * _number(spec.get("repeat_km"))
    warm_km, work_km, cool_km = _warm_and_cool(total, nominal_work)
    phases = [
        _phase(
            "warmup",
            "Einlaufen",
            f"{_de_number(warm_km)} km",
            "Locker und gesprächsfähig einlaufen; RPE 2–3 hat Vorrang vor Pace.",
            easy,
            distance_km=warm_km,
        )
    ]

    load = details.get("load") if isinstance(details.get("load"), dict) else {}
    work_minutes = _number(load.get("high_min")) + _number(load.get("moderate_min"))
    repetitions = int(spec.get("repetitions") or 0)
    repetitions_min = int(spec.get("repetitions_min") or 0)
    repetitions_max = int(spec.get("repetitions_max") or 0)
    work_values: dict[str, Any] = {"distance_km": work_km}
    if mode == "distance_repeats" and repetitions:
        repeat_km = _km(work_km / repetitions)
        target = f"{repetitions} × {_de_number(repeat_km)} km"
        work_values.update(repetitions=repetitions, repeat_distance_km=repeat_km)
    elif mode == "distance_repeat_range" and repetitions_min and repetitions_max:
        target = f"{repetitions_min}–{repetitions_max} × {_de_number(_number(spec.get('repeat_km')))} km"
        work_values.update(repetitions_min=repetitions_min, repetitions_max=repetitions_max, repeat_distance_km=_number(spec.get("repeat_km")))
    elif mode == "time_repeats" and repetitions:
        repeat_s = int(spec.get("repeat_s") or round(work_minutes * 60 / max(repetitions, 1)))
        target = f"{repetitions} × {_seconds_target(repeat_s)}"
        work_values.update(repetitions=repetitions, repeat_duration_s=repeat_s)
    elif mode == "time_repeat_range" and repetitions_min and repetitions_max:
        repeat_s = int(round(work_minutes * 60 / max(repetitions_max, 1))) if work_minutes else 0
        target = f"{repetitions_min}–{repetitions_max} kurze Blöcke"
        work_values.update(repetitions_min=repetitions_min, repetitions_max=repetitions_max, repeat_duration_s=repeat_s or None)
    elif mode in {"structure", "repetition_range"}:
        structure = str(spec.get("structure") or "kontrollierte Reize")
        target = f"{repetitions_min}–{repetitions_max} × {structure}" if repetitions_min and repetitions_max else structure
        work_values.update(repetitions_min=repetitions_min or None, repetitions_max=repetitions_max or None)
    elif mode == "progression":
        stages = int(spec.get("stages") or 3)
        target = f"{_de_number(work_km)} km in {stages} kontrollierten Stufen"
        work_values.update(repetitions=stages)
    elif mode == "mp_blocks":
        repetitions = 3 if work_km >= 7.5 else 2
        repeat_km = _km(work_km / repetitions)
        target = f"{repetitions} × {_de_number(repeat_km)} km"
        work_values.update(repetitions=repetitions, repeat_distance_km=repeat_km)
    else:
        target = f"{_de_number(work_km)} km"
        if work_minutes > 0:
            work_values["duration_s"] = int(round(work_minutes * 60))

    phases.append(
        _phase(
            "work",
            "Hauptteil",
            target,
            _work_instruction(details),
            work_pace,
            **work_values,
        )
    )
    recovery_spec = spec
    if mode == "mp_blocks":
        recovery_spec = {
            **spec,
            "recovery_repetitions": max(1, repetitions - 1),
        }
    recovery = _recovery_phase(recovery_spec, easy)
    if recovery:
        phases.append(recovery)
    phases.append(
        _phase(
            "cooldown",
            "Auslaufen",
            f"{_de_number(cool_km)} km",
            "Bewusst locker auslaufen und die Herzfrequenz kontrolliert absenken.",
            easy,
            distance_km=cool_km,
        )
    )
    return phases


def _long_run_phases(workout: dict[str, Any], details: dict[str, Any]) -> list[dict[str, Any]]:
    total = _km(workout.get("distance_km"))
    variant = str(details.get("variant_key") or "")
    easy = _easy_pace(workout, details)
    stored = _stored_pace(workout)
    if variant == "long_mp_blocks" or _number(details.get("mp_km")) > 0:
        mp_km = min(total, _km(details.get("mp_km")))
        easy_km = max(0.0, total - mp_km)
        warm = _km(min(3.0, max(2.0, easy_km * 0.3)))
        cool = _km(min(2.0, max(1.0, easy_km * 0.2)))
        between = _km(max(0.0, easy_km - warm - cool))
        repetitions = 3 if mp_km >= 8 else 2
        phases = [
            _phase("warmup", "Einlaufen", f"{_de_number(warm)} km", "Ruhig und gesprächsfähig beginnen.", easy, distance_km=warm),
            _phase("work", "Marathonpace-Blöcke", f"{repetitions} × {_de_number(mp_km / repetitions)} km", "Aktuelle Trainings-Marathonpace gleichmäßig halten; nicht schneller werden.", stored, distance_km=mp_km, repetitions=repetitions, repeat_distance_km=_km(mp_km / repetitions)),
        ]
        if between > 0:
            phases.append(_phase("recovery", "Lockere Zwischenabschnitte", f"insgesamt {_de_number(between)} km", "Zwischen den Marathonpace-Blöcken vollständig locker laufen.", easy, distance_km=between, repetitions=max(1, repetitions - 1), counted_in_distance=True))
        phases.append(_phase("cooldown", "Auslaufen", f"{_de_number(cool)} km", "Locker auslaufen; keine zusätzliche Endbeschleunigung.", easy, distance_km=cool))
        return phases
    if variant in {"long_progression", "long_fast_finish"}:
        load = details.get("load") if isinstance(details.get("load"), dict) else {}
        moderate_min = _number(load.get("moderate_min"))
        steady = _steady_pace(details)
        moderate_km = _km(moderate_min * 60 / max(sum(x for x in steady if x) / 2, 1)) if all(steady) and moderate_min else _km(min(4.0, total * 0.18))
        easy_km = _km(max(0.0, total - moderate_km))
        target = _duration_range_target(15 * 60, 20 * 60) if variant == "long_fast_finish" else f"{_de_number(moderate_km)} km"
        return [
            _phase("work", "Lockerer Hauptteil", f"{_de_number(easy_km)} km", "Ruhig und gesprächsfähig laufen; Fueling planmäßig umsetzen.", easy, distance_km=easy_km),
            _phase("work", "Progressiver Schluss", target, "Kontrolliert moderat steigern, klar unter der Schwelle bleiben.", steady, distance_km=moderate_km, duration_min_s=900 if variant == "long_fast_finish" else None, duration_max_s=1200 if variant == "long_fast_finish" else None),
        ]
    label = "Wettkampf" if workout.get("workout_type") == "race" else "Lockerer Dauerlauf"
    instruction = str(details.get("instructions") or "Ruhig und gesprächsfähig laufen.")
    return [_phase("work", label, f"{_de_number(total)} km", instruction, stored, distance_km=total)]


def _easy_phases(workout: dict[str, Any], details: dict[str, Any]) -> list[dict[str, Any]]:
    total = _km(workout.get("distance_km"))
    easy = _stored_pace(workout)
    phases = [_phase("work", "Lockerer Lauf", f"{_de_number(total)} km", "Locker und gesprächsfähig laufen; RPE 2–3 hat Vorrang vor Pace.", easy, distance_km=total)]
    if bool(details.get("strides")):
        phases.append(_phase("work", "Steigerungen", "4–6 kurze Steigerungen", "Locker beschleunigen, technisch sauber bleiben und dazwischen vollständig erholen.", (None, None), repetitions_min=4, repetitions_max=6, counted_in_distance=True))
    return phases


def build_phases(workout: dict[str, Any]) -> list[dict[str, Any]]:
    details = _details(workout)
    workout_type = str(workout.get("workout_type") or "")
    if workout_type in {"quality", "raceprep"}:
        if workout_type == "raceprep" and not details.get("variant_key"):
            details["variant_key"] = "raceprep"
        return _quality_phases(workout, details)
    if workout_type in {"long", "race"}:
        return _long_run_phases(workout, details)
    return _easy_phases(workout, details)


def enrich_workout(workout: dict[str, Any]) -> dict[str, Any]:
    """Return a compatible workout dictionary with structured phase metadata."""
    enriched = dict(workout)
    details = _details(enriched)
    phases = build_phases({**enriched, "details": details})
    for index, phase in enumerate(phases, 1):
        phase["order"] = index
    details["phase_schema_version"] = PHASE_SCHEMA_VERSION
    details["phases"] = phases
    details["phase_summary"] = " · ".join(
        f"{phase['label']}: {phase['target_text']}" for phase in phases
    )
    if any(
        phase.get("kind") == "recovery" and phase.get("counted_in_distance") is False
        for phase in phases
    ):
        details["distance_note"] = (
            "Zeitbasierte Trab-/Gehpausen sind separat ausgewiesen und können "
            "die tatsächlich aufgezeichnete Distanz erhöhen."
        )
    primary = next((phase for phase in phases if phase.get("kind") == "work"), None)
    details["primary_pace_text"] = primary.get("pace_text") if primary else None
    enriched["details"] = details
    return enriched
