from __future__ import annotations

from datetime import datetime
from typing import Any
import re

import health_auto_export_v026 as previous

MIN_TOKEN_LENGTH = 48
MAX_TOKEN_LENGTH = 256
MIN_UNIQUE_TOKEN_CHARS = 8
MAX_BODY_BYTES = previous.MAX_BODY_BYTES


def configured_token() -> str:
    return previous.configured_token()


def token_configuration_error() -> str | None:
    token = configured_token()
    if not token:
        return "Health Auto Export Token ist noch nicht konfiguriert."
    if len(token) < MIN_TOKEN_LENGTH:
        return f"Health Auto Export Token muss mindestens {MIN_TOKEN_LENGTH} Zeichen lang sein."
    if len(token) > MAX_TOKEN_LENGTH:
        return f"Health Auto Export Token darf höchstens {MAX_TOKEN_LENGTH} Zeichen lang sein."
    if token != token.strip() or any(ch.isspace() for ch in token):
        return "Health Auto Export Token darf keine Leerzeichen enthalten."
    if len(set(token)) < MIN_UNIQUE_TOKEN_CHARS:
        return "Health Auto Export Token ist zu gleichförmig. Bitte einen zufällig erzeugten Token verwenden."
    return None


def authorized(authorization: str | None, x_token: str | None) -> bool:
    if token_configuration_error() is not None:
        return False
    return previous.authorized(authorization, x_token)


def _normalized_metric_name(value: Any) -> str:
    text = str(value or "").casefold().replace("₂", "2").replace("&", " and ").replace("+", " plus ")
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    aliases = {
        "heart_rate_variability": "heart_rate_variability",
        "heart_rate_variability_sdnn": "heart_rate_variability_sdnn",
        "resting_heart_rate": "resting_heart_rate",
        "body_mass": "body_mass",
        "weight": "weight",
        "weight_and_body_mass": "weight_&_body_mass",
        "vo2_max": "vo2_max",
        "sleep_analysis": "sleep_analysis",
    }
    return aliases.get(text, text)


def _seconds_between(a: str, b: str) -> float:
    return abs((datetime.fromisoformat(a) - datetime.fromisoformat(b)).total_seconds())


def _validate_existing_run_identity(c, workout: dict[str, Any]) -> tuple[int, str] | None:
    workout_id = str(workout.get("id") or "").strip()
    if not workout_id:
        return None
    row = c.execute(
        "SELECT id,external_id,started_at,distance_km,duration_s,source FROM runs WHERE external_id=?",
        (workout_id,),
    ).fetchone()
    if not row:
        return None
    incoming_start = previous._parse_date(workout.get("start"))
    incoming_distance = previous._distance_km(workout.get("distance"))
    incoming_duration = previous._finite(workout.get("duration"), 1, 172800)
    if _seconds_between(str(row["started_at"]), incoming_start) > 5:
        raise ValueError("Workout-ID kollidiert mit einem vorhandenen Lauf (abweichender Startzeitpunkt).")
    distance_tolerance = max(0.05, float(row["distance_km"]) * 0.01)
    if abs(float(row["distance_km"]) - incoming_distance) > distance_tolerance:
        raise ValueError("Workout-ID kollidiert mit einem vorhandenen Lauf (abweichende Distanz).")
    duration_tolerance = max(5.0, float(row["duration_s"]) * 0.005)
    if abs(float(row["duration_s"]) - incoming_duration) > duration_tolerance:
        raise ValueError("Workout-ID kollidiert mit einem vorhandenen Lauf (abweichende Dauer).")
    return int(row["id"]), str(row["source"] or "")


def _filter_existing_run_points(c, run_id: int, existing_source: str, workout: dict[str, Any]) -> None:
    existing_samples = {
        (str(r["metric_type"]), str(r["sampled_at"]))
        for r in c.execute(
            "SELECT metric_type,sampled_at FROM run_samples WHERE run_id=?",
            (run_id,),
        ).fetchall()
    }
    for field, metric_type in previous.WORKOUT_SERIES.items():
        values = workout.get(field)
        if not isinstance(values, list):
            continue
        filtered = []
        for item in values:
            if not isinstance(item, dict):
                continue
            key = (metric_type, previous._series_time(item))
            if key in existing_samples:
                continue
            existing_samples.add(key)
            filtered.append(item)
        workout[field] = filtered

    cadence = workout.get("stepCadence")
    if isinstance(cadence, dict) and cadence.get("qty") is not None:
        cadence_key = ("cadence", previous._parse_date(workout.get("start")))
        if cadence_key in existing_samples:
            workout.pop("stepCadence", None)

    # A route already imported from the Apple export is considered canonical.
    # Do not create a second parallel route solely because HAE uses a different
    # source label. HAE-originated routes remain incrementally idempotent via the
    # existing UNIQUE(run_id, source, sequence) constraint.
    if existing_source.startswith("apple_health") and existing_source != "apple_health_hae":
        has_route = c.execute(
            "SELECT 1 FROM gps_points WHERE run_id=? LIMIT 1", (run_id,)
        ).fetchone()
        if has_route:
            workout["route"] = []


def _filter_existing_health_metrics(c, metrics: list[Any]) -> None:
    existing = {
        (str(r["metric_type"]), str(r["start_at"]))
        for r in c.execute(
            "SELECT metric_type,start_at FROM health_metrics WHERE metric_type IN "
            "('resting_hr','hrv_sdnn','body_mass','vo2max','sleep_hours')"
        ).fetchall()
    }
    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        canonical = _normalized_metric_name(metric.get("name"))
        metric["name"] = canonical
        if canonical == "sleep_analysis":
            target = "sleep_hours"
        else:
            target = previous.HEALTH_TYPES.get(canonical)
        data = metric.get("data")
        if not target or not isinstance(data, list):
            continue
        filtered = []
        for point in data:
            if not isinstance(point, dict):
                continue
            key = (target, previous._metric_date(point))
            if key in existing:
                continue
            existing.add(key)
            filtered.append(point)
        metric["data"] = filtered


def prepare_payload(c, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("JSON-Objekt erwartet.")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Health Auto Export JSON v2 erwartet ein data-Objekt.")
    workouts = data.get("workouts") or []
    metrics = data.get("metrics") or []
    if not isinstance(workouts, list) or not isinstance(metrics, list):
        raise ValueError("Ungültige Health-Auto-Export-Datenstruktur.")
    for workout in workouts:
        if not isinstance(workout, dict):
            continue
        existing = _validate_existing_run_identity(c, workout)
        if existing:
            _filter_existing_run_points(c, existing[0], existing[1], workout)
    _filter_existing_health_metrics(c, metrics)
    return payload


def ingest(c, payload: dict[str, Any], training) -> dict[str, Any]:
    prepared = prepare_payload(c, payload)
    result = previous.ingest(c, prepared, training, None)
    # Keep compatibility with v0.2.4 performance-mark detection, which expects
    # live Apple Health sources to start with ``apple_health``.
    c.execute("UPDATE runs SET source='apple_health_hae' WHERE source='health_auto_export'")
    return result
