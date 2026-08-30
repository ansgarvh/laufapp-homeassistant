from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_BODY_BYTES = 16 * 1024 * 1024
MAX_WORKOUTS = 20
MAX_WORKOUT_POINTS = 150_000
MAX_ROUTE_POINTS = 50_000
MAX_METRIC_POINTS = 50_000

WORKOUT_SERIES = {
    "heartRateData": "heart_rate",
    "runningSpeed": "running_speed",
    "runningPower": "running_power",
    "runningStrideLength": "stride_length",
    "runningVerticalOscillation": "vertical_oscillation",
    "runningGroundContactTime": "ground_contact_time",
    # Aliases make the parser tolerant of snake_case payload variants.
    "heart_rate_data": "heart_rate",
    "running_speed": "running_speed",
    "running_power": "running_power",
    "running_stride_length": "stride_length",
    "running_vertical_oscillation": "vertical_oscillation",
    "running_ground_contact_time": "ground_contact_time",
}

HEALTH_TYPES = {
    "resting_heart_rate": "resting_hr",
    "heart_rate_variability": "hrv_sdnn",
    "heart_rate_variability_sdnn": "hrv_sdnn",
    "body_mass": "body_mass",
    "weight": "body_mass",
    "weight_&_body_mass": "body_mass",
    "vo2_max": "vo2max",
}


def _options() -> dict[str, Any]:
    path = Path(os.environ.get("LAUFAPP_OPTIONS_FILE", "/data/options.json"))
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def configured_token() -> str:
    return str(
        os.environ.get("LAUFAPP_HEALTH_AUTO_EXPORT_TOKEN")
        or _options().get("health_auto_export_token")
        or ""
    ).strip()


def authorized(authorization: str | None, x_token: str | None) -> bool:
    expected = configured_token()
    if not expected:
        return False
    supplied = (x_token or "").strip()
    if not supplied and authorization:
        prefix, _, value = authorization.partition(" ")
        if prefix.lower() == "bearer":
            supplied = value.strip()
    return bool(supplied) and hmac.compare_digest(supplied, expected)


def _finite(value: Any, minimum: float | None = None, maximum: float | None = None) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Nicht-endlicher Zahlenwert im Health-Auto-Export-Payload.")
    if minimum is not None and number < minimum:
        raise ValueError("Health-Auto-Export-Zahlenwert unterhalb des erlaubten Bereichs.")
    if maximum is not None and number > maximum:
        raise ValueError("Health-Auto-Export-Zahlenwert oberhalb des erlaubten Bereichs.")
    return number


def _parse_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("Health-Auto-Export-Zeitstempel fehlt.")
    formats = ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d")
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            if fmt == "%Y-%m-%d":
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError as exc:
        raise ValueError(f"Ungültiger Health-Auto-Export-Zeitstempel: {text[:48]}") from exc


def _stable_id(*parts: Any) -> str:
    material = "|".join(str(p) for p in parts)
    return "hae:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def _qty(obj: Any, default: float | None = None) -> float | None:
    if not isinstance(obj, dict) or obj.get("qty") is None:
        return default
    return _finite(obj["qty"])


def _unit(obj: Any, default: str = "") -> str:
    return str(obj.get("units") or default)[:40] if isinstance(obj, dict) else default


def _distance_km(obj: Any) -> float:
    qty = _qty(obj)
    if qty is None:
        raise ValueError("Lauf ohne Distanz im Health-Auto-Export-Payload.")
    unit = _unit(obj).lower()
    if unit in {"km", "kilometer", "kilometers"}:
        km = qty
    elif unit in {"mi", "mile", "miles"}:
        km = qty * 1.609344
    elif unit in {"m", "meter", "meters"}:
        km = qty / 1000.0
    else:
        raise ValueError(f"Nicht unterstützte Distanzeinheit: {unit or '?'}")
    return _finite(km, 0.01, 500.0)


def _meters(obj: Any) -> float | None:
    qty = _qty(obj)
    if qty is None:
        return None
    unit = _unit(obj).lower()
    if unit in {"m", "meter", "meters"}:
        return qty
    if unit in {"ft", "feet"}:
        return qty * 0.3048
    return qty


def _kcal(obj: Any) -> float | None:
    qty = _qty(obj)
    if qty is None:
        return None
    unit = _unit(obj).lower()
    if unit == "kj":
        return qty / 4.184
    return qty


def _avg_hr(workout: dict[str, Any]) -> float | None:
    value = _qty(workout.get("avgHeartRate"))
    if value is None and isinstance(workout.get("heartRate"), dict):
        value = _qty(workout["heartRate"].get("avg"))
    return _finite(value, 20, 260) if value is not None else None


def _series_value(item: dict[str, Any], metric_type: str) -> float:
    if metric_type == "heart_rate":
        for key in ("Avg", "avg", "qty"):
            if item.get(key) is not None:
                return _finite(item[key], 20, 260)
    return _finite(item.get("qty"), -1_000_000, 1_000_000)


def _series_time(item: dict[str, Any]) -> str:
    return _parse_date(item.get("date") or item.get("timestamp") or item.get("startDate"))


def _insert_sample(c, run_id: int, workout_id: str, metric_type: str, item: dict[str, Any]) -> int:
    at = _series_time(item)
    value = _series_value(item, metric_type)
    unit = str(item.get("units") or "")[:40]
    external_id = _stable_id("workout", workout_id, metric_type, at, value, item.get("source") or "")
    cur = c.execute(
        "INSERT OR IGNORE INTO run_samples(external_id,run_id,metric_type,sampled_at,value,unit,source) VALUES(?,?,?,?,?,?,?)",
        (external_id, run_id, metric_type, at, value, unit, "health_auto_export"),
    )
    return int(bool(cur.rowcount))


def _insert_workout(c, workout: dict[str, Any], training) -> tuple[int, bool, int, int]:
    workout_id = str(workout.get("id") or "").strip()
    if not workout_id or len(workout_id) > 180:
        raise ValueError("Workout-ID fehlt oder ist ungültig.")
    name = str(workout.get("name") or "").strip().lower()
    if "run" not in name and "lauf" not in name:
        return 0, False, 0, 0
    start = _parse_date(workout.get("start"))
    end = _parse_date(workout.get("end"))
    duration = _finite(workout.get("duration"), 1, 172800)
    distance = _distance_km(workout.get("distance"))
    avg_hr = _avg_hr(workout)
    elevation = _meters(workout.get("elevationUp"))
    calories = _kcal(workout.get("activeEnergyBurned") or workout.get("activeEnergy") or workout.get("totalEnergy"))

    existing = c.execute("SELECT id FROM runs WHERE external_id=?", (workout_id,)).fetchone()
    added = existing is None
    if existing:
        run_id = int(existing["id"])
        c.execute(
            "UPDATE runs SET ended_at=COALESCE(ended_at,?),avg_hr=COALESCE(avg_hr,?),elevation_m=COALESCE(elevation_m,?),calories=COALESCE(calories,?) WHERE id=?",
            (end, avg_hr, elevation, calories, run_id),
        )
    else:
        cur = c.execute(
            "INSERT INTO runs(external_id,started_at,ended_at,distance_km,duration_s,avg_hr,elevation_m,calories,source) VALUES(?,?,?,?,?,?,?,?,?)",
            (workout_id, start, end, distance, duration, avg_hr, elevation, calories, "health_auto_export"),
        )
        run_id = int(cur.lastrowid)
        training.auto_match_run(c, run_id)

    sample_count = 0
    point_count = 0
    for field, metric_type in WORKOUT_SERIES.items():
        values = workout.get(field)
        if values is None:
            continue
        if not isinstance(values, list):
            continue
        point_count += len(values)
        if point_count > MAX_WORKOUT_POINTS:
            raise ValueError("Zu viele Workout-Messpunkte in einer Anfrage.")
        for item in values:
            if isinstance(item, dict):
                sample_count += _insert_sample(c, run_id, workout_id, metric_type, item)

    # HAE documents stepCadence as a workout summary rather than a time series.
    cadence = workout.get("stepCadence")
    if isinstance(cadence, dict) and cadence.get("qty") is not None:
        item = {"date": workout.get("start"), "qty": cadence.get("qty"), "units": cadence.get("units") or "spm"}
        sample_count += _insert_sample(c, run_id, workout_id, "cadence", item)

    route = workout.get("route") or []
    if not isinstance(route, list):
        raise ValueError("Ungültige Routendaten im Workout.")
    if len(route) > MAX_ROUTE_POINTS:
        raise ValueError("Zu viele GPS-Punkte in einem Workout.")
    gps_count = 0
    for sequence, point in enumerate(route):
        if not isinstance(point, dict):
            continue
        at = _parse_date(point.get("timestamp"))
        lat = _finite(point.get("latitude", point.get("lat")), -90, 90)
        lon = _finite(point.get("longitude", point.get("lon")), -180, 180)
        alt = point.get("altitude")
        alt = None if alt is None else _finite(alt, -1000, 12000)
        cur = c.execute(
            "INSERT OR IGNORE INTO gps_points(run_id,sampled_at,latitude,longitude,elevation_m,sequence,source) VALUES(?,?,?,?,?,?,?)",
            (run_id, at, lat, lon, alt, sequence, "health_auto_export"),
        )
        gps_count += int(bool(cur.rowcount))
    return run_id, added, sample_count, gps_count


def _metric_date(point: dict[str, Any]) -> str:
    return _parse_date(point.get("date") or point.get("startDate") or point.get("sleepEnd") or point.get("sleepStart"))


def _insert_health_metric(c, metric_type: str, units: str, point: dict[str, Any], value: float) -> int:
    start = _metric_date(point)
    end_raw = point.get("endDate")
    end = _parse_date(end_raw) if end_raw else None
    source = str(point.get("source") or "")
    external_id = _stable_id("metric", metric_type, start, end or "", value, source)
    cur = c.execute(
        "INSERT OR IGNORE INTO health_metrics(external_id,metric_type,start_at,end_at,value,unit,source) VALUES(?,?,?,?,?,?,?)",
        (external_id, metric_type, start, end, value, units[:40], "health_auto_export"),
    )
    return int(bool(cur.rowcount))


def _insert_metrics(c, metrics: list[Any]) -> int:
    total_points = 0
    inserted = 0
    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        name = str(metric.get("name") or "").strip().lower()
        data = metric.get("data") or []
        if not isinstance(data, list):
            raise ValueError("Ungültige Health-Metrikdaten.")
        total_points += len(data)
        if total_points > MAX_METRIC_POINTS:
            raise ValueError("Zu viele allgemeine Health-Messpunkte in einer Anfrage.")
        units = str(metric.get("units") or "")
        if name == "sleep_analysis":
            for point in data:
                if not isinstance(point, dict):
                    continue
                value = point.get("totalSleep", point.get("asleep", point.get("qty")))
                if value is None:
                    continue
                inserted += _insert_health_metric(c, "sleep_hours", units or "hr", point, _finite(value, 0, 24))
            continue
        target = HEALTH_TYPES.get(name)
        if not target:
            continue
        for point in data:
            if not isinstance(point, dict) or point.get("qty") is None:
                continue
            inserted += _insert_health_metric(c, target, units, point, _finite(point["qty"], -1_000_000, 1_000_000))
    return inserted


def ingest(c, payload: dict[str, Any], training, performance_sync=None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("JSON-Objekt erwartet.")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Health Auto Export JSON v2 erwartet ein data-Objekt.")
    workouts = data.get("workouts") or []
    metrics = data.get("metrics") or []
    if not isinstance(workouts, list) or not isinstance(metrics, list):
        raise ValueError("Ungültige Health-Auto-Export-Datenstruktur.")
    if len(workouts) > MAX_WORKOUTS:
        raise ValueError("Zu viele Workouts in einer Anfrage.")

    result = {
        "workouts_received": len(workouts),
        "runs_added": 0,
        "runs_existing": 0,
        "samples_added": 0,
        "gps_points_added": 0,
        "health_metrics_added": 0,
    }
    for workout in workouts:
        if not isinstance(workout, dict):
            raise ValueError("Ungültiger Workout-Eintrag.")
        run_id, added, samples, gps = _insert_workout(c, workout, training)
        if not run_id:
            continue
        result["runs_added" if added else "runs_existing"] += 1
        result["samples_added"] += samples
        result["gps_points_added"] += gps
    result["health_metrics_added"] = _insert_metrics(c, metrics)
    if performance_sync is not None and (result["runs_added"] or result["runs_existing"]):
        result["performance_marks_detected"] = int(performance_sync(c, training, 24))
    else:
        result["performance_marks_detected"] = 0
    now = datetime.now(timezone.utc).isoformat()
    c.execute(
        "INSERT INTO settings(key,value) VALUES('health_auto_export_last_sync',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (json.dumps(now),),
    )
    c.execute(
        "INSERT INTO settings(key,value) VALUES('health_auto_export_last_result',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (json.dumps(result, ensure_ascii=False),),
    )
    return result
