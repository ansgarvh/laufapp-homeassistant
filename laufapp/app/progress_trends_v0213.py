from __future__ import annotations

import calendar
import math
import sqlite3
from datetime import date, timedelta
from typing import Any


PERIOD_MONTHS = {"3m": 3, "6m": 6, "12m": 12, "24m": 24}
HEALTH_RANGES = {
    "resting_hr": (20.0, 240.0),
    "hrv_sdnn": (0.0, 1000.0),
    "sleep_hours": (0.0, 24.0),
    "body_mass": (20.0, 300.0),
    "vo2max": (5.0, 100.0),
}


def _month_cutoff(today: date, months: int) -> date:
    raw = today.year * 12 + today.month - 1 - months
    year, month0 = divmod(raw, 12)
    month = month0 + 1
    return date(year, month, min(today.day, calendar.monthrange(year, month)[1]))


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def build_training_trends(
    c: sqlite3.Connection,
    period: str,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Return bounded weekly trend data without exposing raw Health/GPS samples."""
    if period not in PERIOD_MONTHS:
        raise ValueError("Ungültiger Zeitraum für Trainingsentwicklung.")

    current = today or date.today()
    cutoff = _month_cutoff(current, PERIOD_MONTHS[period])
    first_week = _week_start(cutoff)
    last_week = _week_start(current)

    buckets: dict[str, dict[str, Any]] = {}
    cursor = first_week
    while cursor <= last_week:
        key = cursor.isoformat()
        buckets[key] = {
            "week_start": key,
            "distance_km": 0.0,
            "run_count": 0,
            "duration_hours": 0.0,
            "longest_run_km": 0.0,
            "elevation_m": 0.0,
            "_pace_distance": 0.0,
            "_pace_duration": 0.0,
            "_hr_weight": 0.0,
            "_hr_duration": 0.0,
            "_cadence_weight": 0.0,
            "_cadence_duration": 0.0,
            "_rpe": [],
            "_health": {name: [] for name in HEALTH_RANGES},
        }
        cursor += timedelta(days=7)

    run_rows = c.execute(
        "SELECT id,started_at,distance_km,duration_s,avg_hr,elevation_m,rpe "
        "FROM runs WHERE substr(started_at,1,10)>=? AND substr(started_at,1,10)<=? "
        "ORDER BY started_at",
        (cutoff.isoformat(), current.isoformat()),
    ).fetchall()

    run_ids = [int(r["id"]) for r in run_rows]
    cadence_by_run: dict[int, float] = {}
    if run_ids:
        placeholders = ",".join("?" for _ in run_ids)
        cadence_rows = c.execute(
            f"SELECT run_id,AVG(value) AS cadence FROM run_samples "
            f"WHERE metric_type='cadence' AND run_id IN ({placeholders}) GROUP BY run_id",
            tuple(run_ids),
        ).fetchall()
        for row in cadence_rows:
            value = _number(row["cadence"])
            if value is not None and 60.0 <= value <= 240.0:
                cadence_by_run[int(row["run_id"])] = value

    coverage = {
        "runs": len(run_rows),
        "pace_runs": 0,
        "heart_rate_runs": 0,
        "cadence_runs": 0,
        "elevation_runs": 0,
        "rpe_runs": 0,
        "resting_hr_samples": 0,
        "hrv_sdnn_samples": 0,
        "sleep_hours_samples": 0,
        "body_mass_samples": 0,
        "vo2max_samples": 0,
    }

    for row in run_rows:
        try:
            run_day = date.fromisoformat(str(row["started_at"])[:10])
        except ValueError:
            continue
        bucket = buckets.get(_week_start(run_day).isoformat())
        if bucket is None:
            continue

        distance = _number(row["distance_km"])
        duration = _number(row["duration_s"])
        if distance is None or duration is None or distance <= 0 or duration <= 0:
            continue

        bucket["distance_km"] += distance
        bucket["run_count"] += 1
        bucket["duration_hours"] += duration / 3600.0
        bucket["longest_run_km"] = max(bucket["longest_run_km"], distance)
        bucket["_pace_distance"] += distance
        bucket["_pace_duration"] += duration
        coverage["pace_runs"] += 1

        avg_hr = _number(row["avg_hr"])
        if avg_hr is not None and 20.0 <= avg_hr <= 260.0:
            bucket["_hr_weight"] += avg_hr * duration
            bucket["_hr_duration"] += duration
            coverage["heart_rate_runs"] += 1

        cadence = cadence_by_run.get(int(row["id"]))
        if cadence is not None:
            bucket["_cadence_weight"] += cadence * duration
            bucket["_cadence_duration"] += duration
            coverage["cadence_runs"] += 1

        elevation = _number(row["elevation_m"])
        if elevation is not None and 0.0 <= elevation <= 20_000.0:
            bucket["elevation_m"] += elevation
            coverage["elevation_runs"] += 1

        rpe = _number(row["rpe"])
        if rpe is not None and 1.0 <= rpe <= 10.0:
            bucket["_rpe"].append(rpe)
            coverage["rpe_runs"] += 1

    health_rows = c.execute(
        "SELECT metric_type,start_at,value FROM health_metrics "
        "WHERE metric_type IN ('resting_hr','hrv_sdnn','sleep_hours','body_mass','vo2max') "
        "AND substr(start_at,1,10)>=? AND substr(start_at,1,10)<=? ORDER BY start_at",
        (cutoff.isoformat(), current.isoformat()),
    ).fetchall()
    for row in health_rows:
        metric = str(row["metric_type"])
        bounds = HEALTH_RANGES.get(metric)
        value = _number(row["value"])
        if bounds is None or value is None or not bounds[0] <= value <= bounds[1]:
            continue
        try:
            metric_day = date.fromisoformat(str(row["start_at"])[:10])
        except ValueError:
            continue
        bucket = buckets.get(_week_start(metric_day).isoformat())
        if bucket is None:
            continue
        bucket["_health"][metric].append(value)
        coverage[f"{metric}_samples"] += 1

    weeks: list[dict[str, Any]] = []
    for bucket in buckets.values():
        distance = float(bucket["distance_km"])
        duration = float(bucket["_pace_duration"])
        point = {
            "week_start": bucket["week_start"],
            "distance_km": round(distance, 2),
            "run_count": int(bucket["run_count"]),
            "duration_hours": round(float(bucket["duration_hours"]), 2),
            "avg_pace_s_per_km": round(duration / float(bucket["_pace_distance"]), 2)
            if bucket["_pace_distance"]
            else None,
            "avg_run_km": round(distance / int(bucket["run_count"]), 2)
            if bucket["run_count"]
            else None,
            "longest_run_km": round(float(bucket["longest_run_km"]), 2)
            if bucket["run_count"]
            else None,
            "avg_hr": round(float(bucket["_hr_weight"]) / float(bucket["_hr_duration"]), 1)
            if bucket["_hr_duration"]
            else None,
            "cadence_spm": round(float(bucket["_cadence_weight"]) / float(bucket["_cadence_duration"]), 1)
            if bucket["_cadence_duration"]
            else None,
            "elevation_m": round(float(bucket["elevation_m"]), 1)
            if bucket["run_count"] and bucket["elevation_m"]
            else None,
            "avg_rpe": round(_mean(bucket["_rpe"]), 1) if bucket["_rpe"] else None,
        }
        for metric in HEALTH_RANGES:
            values = bucket["_health"][metric]
            point[metric] = round(_mean(values), 2) if values else None
        weeks.append(point)

    return {
        "period": period,
        "cutoff_date": cutoff.isoformat(),
        "through_date": current.isoformat(),
        "weeks": weeks,
        "coverage": coverage,
    }
