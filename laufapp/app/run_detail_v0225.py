from __future__ import annotations

import json
import math
import statistics
from typing import Any

from training import parse_dt

MAX_SERIES_POINTS = 240
MAX_ROUTE_POINTS = 700


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _downsample(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Evenly thin a single-run series while always retaining both endpoints."""
    if len(items) <= limit:
        return items
    if limit <= 1:
        return items[:1]
    indexes = {
        round(i * (len(items) - 1) / (limit - 1))
        for i in range(limit)
    }
    return [items[i] for i in sorted(indexes)]


def _elapsed_seconds(started_at: str, ended_at: str | None, duration_s: float) -> float:
    if ended_at:
        try:
            elapsed = (parse_dt(ended_at) - parse_dt(started_at)).total_seconds()
            # A bad source timestamp must not make the detail screen nonsensical.
            if elapsed >= duration_s * 0.95 and elapsed <= max(duration_s + 6 * 3600, duration_s * 2):
                return float(elapsed)
        except Exception:
            pass
    return float(duration_s)


def _time_offset(sampled_at: str, started_at: str) -> float | None:
    try:
        return max(0.0, (parse_dt(sampled_at) - parse_dt(started_at)).total_seconds())
    except Exception:
        return None


def _normalize_sample(metric: str, value: float, unit: str) -> tuple[float, str] | None:
    u = str(unit or "").strip().casefold().replace(" ", "")
    if metric == "heart_rate":
        return (value, "bpm") if 20 <= value <= 260 else None
    if metric == "running_power":
        return (value, "W") if 0 <= value <= 3000 else None
    if metric == "cadence":
        return (value, "spm") if 20 <= value <= 300 else None
    if metric == "total_calories":
        if u in {"kj", "kilojoule", "kilojoules"}:
            value /= 4.184
        elif u not in {"", "kcal", "kilocalorie", "kilocalories"}:
            return None
        return (value, "kcal") if 0 <= value <= 10000 else None
    if metric == "stride_length":
        if u in {"cm", "centimeter", "centimeters"}:
            value /= 100.0
        elif u in {"mm", "millimeter", "millimeters"}:
            value /= 1000.0
        return (value, "m") if 0.1 <= value <= 4 else None
    if metric == "vertical_oscillation":
        if u in {"m", "meter", "meters"}:
            value *= 100.0
        elif u in {"mm", "millimeter", "millimeters"}:
            value /= 10.0
        return (value, "cm") if 0 <= value <= 50 else None
    if metric == "ground_contact_time":
        if u in {"s", "sec", "second", "seconds"}:
            value *= 1000.0
        return (value, "ms") if 20 <= value <= 1000 else None
    if metric == "running_speed":
        if u in {"km/hr", "km/h", "kmph", "kph"}:
            value /= 3.6
        elif u in {"mi/hr", "mph"}:
            value *= 0.44704
        # Apple-Health XML is normalized to m/s before storage. HAE normally
        # supplies m/s or km/h. Unknown units are accepted only in a plausible
        # m/s range; we never guess that an arbitrary value is km/h.
        elif u not in {"", "m/s", "m/sec", "meter/second", "meters/second"}:
            return None
        return (value, "m/s") if 0.25 <= value <= 15 else None
    return None


def _sample_series(c, run_id: int, metric: str, started_at: str) -> dict[str, Any] | None:
    values: list[float] = []
    points: list[dict[str, Any]] = []
    canonical_unit = ""
    for row in c.execute(
        "SELECT sampled_at,value,unit FROM run_samples WHERE run_id=? AND metric_type=? ORDER BY sampled_at,id",
        (run_id, metric),
    ).fetchall():
        raw = _finite(row["value"])
        if raw is None:
            continue
        normalized = _normalize_sample(metric, raw, str(row["unit"] or ""))
        if normalized is None:
            continue
        value, canonical_unit = normalized
        values.append(value)
        point: dict[str, Any] = {"value": round(value, 4)}
        offset = _time_offset(str(row["sampled_at"]), started_at)
        if offset is not None:
            point["t"] = round(offset, 2)
        points.append(point)
    if not values:
        return None
    return {
        "average": round(statistics.fmean(values), 3),
        "minimum": round(min(values), 3),
        "maximum": round(max(values), 3),
        "samples": len(values),
        "unit": canonical_unit,
        "points": _downsample(points, MAX_SERIES_POINTS),
    }


def _pace_series(speed: dict[str, Any] | None) -> dict[str, Any] | None:
    if not speed:
        return None
    pace_points: list[dict[str, Any]] = []
    all_values: list[float] = []
    for point in speed.get("points", []):
        v = _finite(point.get("value"))
        if v is None or v <= 0:
            continue
        pace = 1000.0 / v
        # Ignore obvious GPS/sensor pauses and impossible spikes in the visual
        # chart. The authoritative average pace remains duration / distance.
        if 120 <= pace <= 1800:
            item = {"value": round(pace, 3)}
            if point.get("t") is not None:
                item["t"] = point["t"]
            pace_points.append(item)
            all_values.append(pace)
    if not all_values:
        return None
    return {
        "average": round(statistics.fmean(all_values), 3),
        "minimum": round(min(all_values), 3),
        "maximum": round(max(all_values), 3),
        "samples": int(speed.get("samples") or len(all_values)),
        "unit": "s/km",
        "points": pace_points,
    }


def _route(c, run_id: int, started_at: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    raw = c.execute(
        "SELECT sampled_at,latitude,longitude,elevation_m,sequence FROM gps_points WHERE run_id=? ORDER BY sequence,id",
        (run_id,),
    ).fetchall()
    route_points: list[dict[str, Any]] = []
    elevation_values: list[float] = []
    elevation_points: list[dict[str, Any]] = []
    for row in raw:
        lat = _finite(row["latitude"])
        lon = _finite(row["longitude"])
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        point: dict[str, Any] = {"lat": round(lat, 7), "lon": round(lon, 7)}
        elevation = _finite(row["elevation_m"])
        if elevation is not None:
            point["elevation_m"] = round(elevation, 2)
            elevation_values.append(elevation)
            ep: dict[str, Any] = {"value": round(elevation, 3)}
            offset = _time_offset(str(row["sampled_at"]), started_at)
            if offset is not None:
                ep["t"] = round(offset, 2)
            elevation_points.append(ep)
        route_points.append(point)
    if not route_points:
        return {
            "available": False,
            "original_points": 0,
            "points": [],
            "privacy_note": "Keine GPS-Route für diesen Lauf gespeichert.",
        }, None
    lats = [p["lat"] for p in route_points]
    lons = [p["lon"] for p in route_points]
    route = {
        "available": True,
        "original_points": len(route_points),
        "points": _downsample(route_points, MAX_ROUTE_POINTS),
        "bounds": {
            "min_lat": min(lats),
            "max_lat": max(lats),
            "min_lon": min(lons),
            "max_lon": max(lons),
        },
        "privacy_note": "Die GPS-Linie wird lokal gezeichnet; es werden keine Koordinaten an einen externen Kartenserver gesendet.",
    }
    elevation_series = None
    if elevation_values:
        elevation_series = {
            "average": round(statistics.fmean(elevation_values), 3),
            "minimum": round(min(elevation_values), 3),
            "maximum": round(max(elevation_values), 3),
            "samples": len(elevation_values),
            "unit": "m",
            "points": _downsample(elevation_points, MAX_SERIES_POINTS),
        }
    return route, elevation_series


def _effort_label(rpe: int | None) -> str | None:
    if rpe is None:
        return None
    if rpe <= 2:
        return "Sehr locker"
    if rpe <= 4:
        return "Locker"
    if rpe <= 6:
        return "Mäßig"
    if rpe <= 8:
        return "Hart"
    return "Sehr hart"


def _linked_workout(c, run_id: int) -> dict[str, Any] | None:
    row = c.execute(
        "SELECT id,title,workout_type,scheduled_date,distance_km,pace_low_s_per_km,pace_high_s_per_km,status,details_json "
        "FROM workouts WHERE linked_run_id=? ORDER BY id DESC LIMIT 1",
        (run_id,),
    ).fetchone()
    if not row:
        return None
    out = dict(row)
    try:
        details = json.loads(out.pop("details_json") or "{}")
    except (TypeError, ValueError):
        details = {}
    out["details"] = details if isinstance(details, dict) else {}
    return out


def build_run_detail(c, run_id: int) -> dict[str, Any]:
    run = c.execute(
        "SELECT r.*,s.brand shoe_brand,s.model shoe_model,s.nickname shoe_nickname "
        "FROM runs r LEFT JOIN shoes s ON s.id=r.shoe_id WHERE r.id=?",
        (run_id,),
    ).fetchone()
    if not run:
        raise KeyError("Lauf nicht gefunden.")
    run_dict = dict(run)
    started_at = str(run["started_at"])
    distance = float(run["distance_km"])
    duration = float(run["duration_s"])

    series: dict[str, Any] = {}
    for metric in (
        "heart_rate",
        "running_speed",
        "running_power",
        "cadence",
        "stride_length",
        "vertical_oscillation",
        "ground_contact_time",
        "total_calories",
    ):
        item = _sample_series(c, run_id, metric, started_at)
        if item:
            series[metric] = item
    pace = _pace_series(series.get("running_speed"))
    if pace:
        series["pace"] = pace

    route, elevation_series = _route(c, run_id, started_at)
    if elevation_series:
        series["elevation"] = elevation_series

    hr = _finite(run["avg_hr"])
    if hr is None and series.get("heart_rate"):
        hr = float(series["heart_rate"]["average"])
    elevation_gain = _finite(run["elevation_m"])
    calories = _finite(run["calories"])
    total_calories = float(series["total_calories"]["average"]) if series.get("total_calories") else None
    rpe = int(run["rpe"]) if run["rpe"] is not None else None

    def average(metric: str) -> float | None:
        item = series.get(metric)
        return float(item["average"]) if item and item.get("average") is not None else None

    summary = {
        "distance_km": round(distance, 3),
        "training_time_s": round(duration, 2),
        "elapsed_time_s": round(_elapsed_seconds(started_at, run["ended_at"], duration), 2),
        "pace_s_per_km": round(duration / max(distance, 0.001), 2),
        "elevation_gain_m": round(elevation_gain, 1) if elevation_gain is not None else None,
        "average_heart_rate_bpm": round(hr, 1) if hr is not None else None,
        "average_power_w": round(average("running_power"), 1) if average("running_power") is not None else None,
        "average_cadence_spm": round(average("cadence"), 1) if average("cadence") is not None else None,
        "active_calories_kcal": round(calories, 1) if calories is not None else None,
        "total_calories_kcal": round(total_calories, 1) if total_calories is not None else None,
        "effort_rpe": rpe,
        "effort_label": _effort_label(rpe),
        "stride_length_m": round(average("stride_length"), 3) if average("stride_length") is not None else None,
        "vertical_oscillation_cm": round(average("vertical_oscillation"), 2) if average("vertical_oscillation") is not None else None,
        "ground_contact_time_ms": round(average("ground_contact_time"), 1) if average("ground_contact_time") is not None else None,
    }

    total_note = (
        "Gesamtkalorien wurden separat aus Health Auto Export übernommen."
        if total_calories is not None
        else "Für diesen Lauf ist kein separat gespeicherter Gesamtenergie-Wert vorhanden; die App schätzt ihn deshalb nicht aus den Aktivitätskalorien."
    )
    return {
        "schema": 1,
        "run": run_dict,
        "workout": _linked_workout(c, run_id),
        "summary": summary,
        "series": series,
        "route": route,
        "notes": {
            "total_calories": total_note,
            "map": route["privacy_note"],
        },
    }
