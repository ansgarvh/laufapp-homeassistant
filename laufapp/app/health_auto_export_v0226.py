"""Health Auto Export v2 compatibility for recovery and body metrics.

Health Auto Export's current metric identifiers use ``weight_body_mass`` and
``vo2max``.  Its sleep payload exposes sleep stages (core, REM and deep) rather
than the historical ``totalSleep`` field.  This layer normalizes those current
shapes before delegating to the established, security-hardened importer.
"""

from __future__ import annotations

import math
import re
from typing import Any

import health_auto_export_v0212 as previous
import health_auto_export_v026 as base


MIN_TOKEN_LENGTH = previous.MIN_TOKEN_LENGTH
MAX_TOKEN_LENGTH = previous.MAX_TOKEN_LENGTH
MIN_UNIQUE_TOKEN_CHARS = previous.MIN_UNIQUE_TOKEN_CHARS
MAX_BODY_BYTES = previous.MAX_BODY_BYTES

_MASS_TO_KG = {
    "kg": 1.0,
    "kilogram": 1.0,
    "kilograms": 1.0,
    "g": 0.001,
    "gram": 0.001,
    "grams": 0.001,
    "lb": 0.45359237,
    "lbs": 0.45359237,
    "pound": 0.45359237,
    "pounds": 0.45359237,
    "st": 6.35029318,
    "stone": 6.35029318,
}

_DURATION_TO_HOURS = {
    "h": 1.0,
    "hr": 1.0,
    "hrs": 1.0,
    "hour": 1.0,
    "hours": 1.0,
    "min": 1.0 / 60.0,
    "mins": 1.0 / 60.0,
    "minute": 1.0 / 60.0,
    "minutes": 1.0 / 60.0,
    "s": 1.0 / 3600.0,
    "sec": 1.0 / 3600.0,
    "secs": 1.0 / 3600.0,
    "second": 1.0 / 3600.0,
    "seconds": 1.0 / 3600.0,
}


def configured_token() -> str:
    return previous.configured_token()


def token_configuration_error() -> str | None:
    return previous.token_configuration_error()


def authorized(authorization: str | None, x_token: str | None) -> bool:
    return previous.authorized(authorization, x_token)


def _name(value: Any) -> str:
    text = str(value or "").casefold().replace("₂", "2").replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _unit(value: Any) -> str:
    return re.sub(r"[\s._-]+", "", str(value or "").casefold())


def _finite(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Ungültiger Health-Auto-Export-Wert für {label}.") from exc
    if not math.isfinite(number):
        raise ValueError(f"Nicht-endlicher Health-Auto-Export-Wert für {label}.")
    return number


def _bounded(value: Any, label: str, minimum: float, maximum: float) -> float:
    number = _finite(value, label)
    if not minimum <= number <= maximum:
        raise ValueError(
            f"Health-Auto-Export-Wert für {label} liegt außerhalb des erlaubten Bereichs."
        )
    return number


def _mass_kg(value: Any, units: Any) -> float:
    normalized = _unit(units)
    factor = _MASS_TO_KG.get(normalized)
    if factor is None:
        raise ValueError(
            f"Nicht unterstützte Gewichtseinheit in Health Auto Export: {str(units or '?')[:24]}"
        )
    return _bounded(_finite(value, "Gewicht") * factor, "Gewicht", 20.0, 300.0)


def _hours(value: Any, units: Any) -> float:
    normalized = _unit(units)
    factor = _DURATION_TO_HOURS.get(normalized)
    if factor is None:
        raise ValueError(
            f"Nicht unterstützte Schlafdauer-Einheit in Health Auto Export: {str(units or '?')[:24]}"
        )
    return _bounded(_finite(value, "Schlaf") * factor, "Schlaf", 0.0, 24.0)


def _sleep_hours(point: dict[str, Any], units: Any) -> float | None:
    for key in ("totalSleep", "asleep", "qty"):
        if point.get(key) is not None:
            return _hours(point[key], point.get("units") or units)

    stage_values = [point.get(key) for key in ("core", "rem", "deep")]
    if not any(value is not None for value in stage_values):
        return None
    total = sum(
        _finite(value, "Schlafphase") for value in stage_values if value is not None
    )
    return _hours(total, point.get("units") or units)


def _normalize_metrics(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    # The request body is already a private, per-request object and the legacy
    # importer normalizes it in place as well. Avoid cloning potentially large
    # workout/GPS time series merely to adjust a handful of health metrics.
    normalized = payload
    data = normalized.get("data") if isinstance(normalized, dict) else None
    metrics = data.get("metrics") if isinstance(data, dict) else None
    if not isinstance(metrics, list):
        return normalized, {}

    seen: dict[str, int] = {}
    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        canonical = _name(metric.get("name"))
        points = metric.get("data")
        if not isinstance(points, list):
            continue
        units = metric.get("units")

        if canonical in {
            "weight_body_mass",
            "weight_and_body_mass",
            "body_mass",
            "weight",
        }:
            metric["name"] = "body_mass"
            metric["units"] = "kg"
            for point in points:
                if isinstance(point, dict) and point.get("qty") is not None:
                    point["qty"] = _mass_kg(point["qty"], point.get("units") or units)
            seen["body_mass"] = seen.get("body_mass", 0) + len(points)
            continue

        if canonical in {"vo2max", "vo2_max"}:
            metric["name"] = "vo2_max"
            metric["units"] = "mL/kg/min"
            for point in points:
                if isinstance(point, dict) and point.get("qty") is not None:
                    point["qty"] = _bounded(point["qty"], "VO2max", 5.0, 100.0)
            seen["vo2max"] = seen.get("vo2max", 0) + len(points)
            continue

        if canonical in {"heart_rate_variability", "heart_rate_variability_sdnn"}:
            metric["name"] = canonical
            for point in points:
                if not isinstance(point, dict) or point.get("qty") is None:
                    continue
                point_unit = _unit(point.get("units") or units)
                value = _finite(point["qty"], "HRV")
                if point_unit in {"s", "sec", "secs", "second", "seconds"}:
                    value *= 1000.0
                elif point_unit not in {"ms", "millisecond", "milliseconds"}:
                    raise ValueError(
                        f"Nicht unterstützte HRV-Einheit in Health Auto Export: {str(point.get('units') or units or '?')[:24]}"
                    )
                point["qty"] = _bounded(value, "HRV", 1.0, 1000.0)
            metric["units"] = "ms"
            seen["hrv_sdnn"] = seen.get("hrv_sdnn", 0) + len(points)
            continue

        if canonical == "resting_heart_rate":
            metric["name"] = canonical
            metric["units"] = "bpm"
            for point in points:
                if isinstance(point, dict) and point.get("qty") is not None:
                    point["qty"] = _bounded(point["qty"], "Ruhepuls", 20.0, 260.0)
            seen["resting_hr"] = seen.get("resting_hr", 0) + len(points)
            continue

        if canonical == "sleep_analysis":
            metric["name"] = canonical
            metric["units"] = "h"
            for point in points:
                if not isinstance(point, dict):
                    continue
                value = _sleep_hours(point, units)
                if value is not None:
                    point["totalSleep"] = value
                if not point.get("startDate") and point.get("sleepStart"):
                    point["startDate"] = point["sleepStart"]
                if not point.get("endDate") and point.get("sleepEnd"):
                    point["endDate"] = point["sleepEnd"]
            seen["sleep_hours"] = seen.get("sleep_hours", 0) + len(points)

    return normalized, seen


def _repair_legacy_pound_rows(c) -> int:
    rows = c.execute(
        "SELECT id,value FROM health_metrics "
        "WHERE metric_type='body_mass' AND source='health_auto_export' "
        "AND lower(trim(unit)) IN ('lb','lbs','pound','pounds')"
    ).fetchall()
    repaired = 0
    for row in rows:
        kg = _bounded(float(row["value"]) * _MASS_TO_KG["lb"], "Gewicht", 20.0, 300.0)
        c.execute(
            "UPDATE health_metrics SET value=?,unit='kg' WHERE id=?",
            (kg, int(row["id"])),
        )
        repaired += 1
    return repaired


def _refresh_existing_hae_metrics(c, payload: dict[str, Any]) -> int:
    """Update a repeated HAE sample when Apple has refined its value.

    A seven-day overlap can send the same sleep night before and after final
    sleep-stage processing.  The older dedupe layer correctly prevents
    duplicates but also kept the first partial value forever.  Only rows owned
    by Health Auto Export are refreshed; canonical XML-import rows are never
    overwritten.
    """
    data = payload.get("data") if isinstance(payload, dict) else None
    metrics = data.get("metrics") if isinstance(data, dict) else None
    if not isinstance(metrics, list):
        return 0

    targets = {
        "body_mass": ("body_mass", "qty"),
        "vo2_max": ("vo2max", "qty"),
        "heart_rate_variability": ("hrv_sdnn", "qty"),
        "heart_rate_variability_sdnn": ("hrv_sdnn", "qty"),
        "resting_heart_rate": ("resting_hr", "qty"),
        "sleep_analysis": ("sleep_hours", "totalSleep"),
    }
    updated = 0
    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        target = targets.get(str(metric.get("name") or ""))
        points = metric.get("data")
        if target is None or not isinstance(points, list):
            continue
        metric_type, value_key = target
        units = str(metric.get("units") or "")[:40]
        for point in points:
            if not isinstance(point, dict) or point.get(value_key) is None:
                continue
            start = base._metric_date(point)
            end_raw = point.get("endDate")
            end = base._parse_date(end_raw) if end_raw else None
            value = _finite(point[value_key], metric_type)
            row = c.execute(
                "SELECT id,value,unit,end_at FROM health_metrics "
                "WHERE metric_type=? AND start_at=? AND source='health_auto_export' "
                "ORDER BY id DESC LIMIT 1",
                (metric_type, start),
            ).fetchone()
            if not row:
                continue
            if (
                abs(float(row["value"]) - value) <= 1e-9
                and str(row["unit"] or "") == units
                and (str(row["end_at"]) if row["end_at"] is not None else None) == end
            ):
                continue
            c.execute(
                "UPDATE health_metrics SET value=?,unit=?,end_at=? WHERE id=?",
                (value, units, end, int(row["id"])),
            )
            updated += 1
    return updated


def ingest(c, payload: dict[str, Any], training) -> dict[str, Any]:
    normalized, seen = _normalize_metrics(payload)
    repaired = _repair_legacy_pound_rows(c)
    updated = _refresh_existing_hae_metrics(c, normalized)
    result = previous.ingest(c, normalized, training)
    result["health_metric_records_seen"] = seen
    result["health_metrics_updated"] = updated
    result["legacy_weight_rows_repaired"] = repaired
    return result
