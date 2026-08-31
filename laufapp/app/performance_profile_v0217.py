from __future__ import annotations

import json
import math
import sqlite3
from datetime import date, timedelta
from statistics import median
from typing import Any

from db import get_setting
import training as base

PROFILE_VERSION = 2
PROFILE_WINDOW_WEEKS = 8


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _round_or_none(value: float | None, digits: int = 1) -> float | None:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def _race_targets(distance_km: float) -> tuple[str, float, float, int]:
    if distance_km >= 40:
        return "Marathon-Readiness", 55.0, 30.0, 4
    if distance_km >= 20:
        return "Halbmarathon-Readiness", 45.0, 20.0, 3
    if distance_km >= 9:
        return "10-km-Readiness", 35.0, 14.0, 3
    return "5-km-Readiness", 30.0, 10.0, 2


def _completed_week_buckets(c: sqlite3.Connection, today: date) -> list[dict[str, float]]:
    current_ws = base.week_start_for(today)
    first_ws = current_ws - timedelta(days=7 * PROFILE_WINDOW_WEEKS)
    buckets: dict[str, dict[str, float]] = {}
    for i in range(PROFILE_WINDOW_WEEKS):
        ws = first_ws + timedelta(days=7 * i)
        buckets[ws.isoformat()] = {"km": 0.0, "seconds": 0.0, "runs": 0.0}
    rows = c.execute(
        "SELECT started_at,distance_km,duration_s FROM runs "
        "WHERE substr(started_at,1,10)>=? AND substr(started_at,1,10)<? ORDER BY started_at",
        (first_ws.isoformat(), current_ws.isoformat()),
    ).fetchall()
    for row in rows:
        try:
            day = date.fromisoformat(str(row["started_at"])[:10])
        except ValueError:
            continue
        key = base.week_start_for(day).isoformat()
        if key not in buckets:
            continue
        km = float(row["distance_km"] or 0)
        sec = float(row["duration_s"] or 0)
        if km <= 0 or sec <= 0:
            continue
        buckets[key]["km"] += km
        buckets[key]["seconds"] += sec
        buckets[key]["runs"] += 1
    return [buckets[k] for k in sorted(buckets)]


def _recent_runs(c: sqlite3.Connection, today: date, days: int = 56) -> list[sqlite3.Row]:
    cutoff = (today - timedelta(days=days)).isoformat()
    return c.execute(
        "SELECT id,started_at,distance_km,duration_s,avg_hr FROM runs "
        "WHERE substr(started_at,1,10)>=? AND substr(started_at,1,10)<=? ORDER BY started_at",
        (cutoff, today.isoformat()),
    ).fetchall()


def _easy_efficiency_trend(c: sqlite3.Connection, today: date) -> dict[str, Any]:
    cutoff = (today - timedelta(days=56)).isoformat()
    rows = c.execute(
        "SELECT r.started_at,r.distance_km,r.duration_s,r.avg_hr "
        "FROM workouts w JOIN runs r ON r.id=w.linked_run_id "
        "WHERE w.workout_type='easy' AND w.status='completed' "
        "AND r.avg_hr BETWEEN 70 AND 220 AND r.distance_km>0 AND r.duration_s>0 "
        "AND substr(r.started_at,1,10)>=? AND substr(r.started_at,1,10)<=? "
        "ORDER BY r.started_at",
        (cutoff, today.isoformat()),
    ).fetchall()
    split = today - timedelta(days=28)
    previous: list[tuple[float, float]] = []
    recent: list[tuple[float, float]] = []
    for row in rows:
        try:
            d = date.fromisoformat(str(row["started_at"])[:10])
        except ValueError:
            continue
        km = float(row["distance_km"] or 0)
        sec = float(row["duration_s"] or 0)
        hr = float(row["avg_hr"] or 0)
        if km <= 0 or sec <= 0 or hr <= 0:
            continue
        efficiency = (km / (sec / 3600.0)) / hr  # km/h per bpm; trend only.
        target = recent if d >= split else previous
        target.append((efficiency, sec))

    def weighted(values: list[tuple[float, float]]) -> float | None:
        denom = sum(w for _, w in values)
        return sum(v * w for v, w in values) / denom if denom > 0 else None

    if len(previous) < 2 or len(recent) < 2:
        return {"change_pct": None, "recent_runs": len(recent), "previous_runs": len(previous)}
    old = weighted(previous)
    new = weighted(recent)
    if not old or not new:
        return {"change_pct": None, "recent_runs": len(recent), "previous_runs": len(previous)}
    return {
        "change_pct": round((new / old - 1.0) * 100.0, 1),
        "recent_runs": len(recent),
        "previous_runs": len(previous),
    }


def _plan_adherence(c: sqlite3.Connection, today: date) -> dict[str, Any]:
    cutoff = (today - timedelta(days=56)).isoformat()
    rows = c.execute(
        "SELECT status,workout_type,scheduled_date FROM workouts "
        "WHERE scheduled_date>=? AND scheduled_date<? ORDER BY scheduled_date",
        (cutoff, today.isoformat()),
    ).fetchall()
    total = len(rows)
    completed = sum(str(r["status"]) == "completed" for r in rows)
    quality_rows = [r for r in rows if str(r["workout_type"]) in {"quality", "raceprep"}]
    quality_completed = sum(str(r["status"]) == "completed" for r in quality_rows)
    specific_rows = [r for r in rows if str(r["workout_type"]) in {"quality", "raceprep", "long"}]
    specific_completed = sum(str(r["status"]) == "completed" for r in specific_rows)
    return {
        "total": total,
        "completed": completed,
        "score": 100.0 * completed / total if total >= 4 else None,
        "quality_total": len(quality_rows),
        "quality_completed": quality_completed,
        "quality_score": 100.0 * quality_completed / len(quality_rows) if len(quality_rows) >= 2 else None,
        "specific_total": len(specific_rows),
        "specific_completed": specific_completed,
        "specific_score": 100.0 * specific_completed / len(specific_rows) if len(specific_rows) >= 2 else None,
    }


def _health_context(c: sqlite3.Connection, today: date) -> dict[str, Any]:
    cutoff = (today - timedelta(days=28)).isoformat()
    rows = c.execute(
        "SELECT metric_type,start_at,value FROM health_metrics "
        "WHERE metric_type IN ('resting_hr','hrv_sdnn','sleep_hours','vo2max') "
        "AND substr(start_at,1,10)>=? AND substr(start_at,1,10)<=? ORDER BY start_at",
        (cutoff, today.isoformat()),
    ).fetchall()
    values: dict[str, list[float]] = {"resting_hr": [], "hrv_sdnn": [], "sleep_hours": [], "vo2max": []}
    bounds = {
        "resting_hr": (20.0, 240.0),
        "hrv_sdnn": (0.0, 1000.0),
        "sleep_hours": (0.0, 24.0),
        "vo2max": (5.0, 100.0),
    }
    for row in rows:
        metric = str(row["metric_type"])
        try:
            value = float(row["value"])
        except (TypeError, ValueError):
            continue
        lo, hi = bounds[metric]
        if math.isfinite(value) and lo <= value <= hi:
            values[metric].append(value)
    return {
        "resting_hr": _round_or_none(sum(values["resting_hr"]) / len(values["resting_hr"]) if values["resting_hr"] else None, 1),
        "hrv_sdnn": _round_or_none(sum(values["hrv_sdnn"]) / len(values["hrv_sdnn"]) if values["hrv_sdnn"] else None, 1),
        "sleep_hours": _round_or_none(sum(values["sleep_hours"]) / len(values["sleep_hours"]) if values["sleep_hours"] else None, 2),
        "vo2max": _round_or_none(values["vo2max"][-1] if values["vo2max"] else None, 1),
    }


def _performance_retention(short: dict[str, Any] | None, long: dict[str, Any] | None, short_km: float, long_km: float) -> tuple[float | None, float | None]:
    if not short or not long:
        return None, None
    expected = base.riegel(float(short["predicted_seconds"]), short_km, long_km, 1.06)
    actual = float(long["predicted_seconds"])
    if expected <= 0:
        return None, None
    extra_fade_pct = max(0.0, (actual / expected - 1.0) * 100.0)
    score = _clamp(100.0 - 5.0 * extra_fade_pct, 25.0, 100.0)
    return score, round(extra_fade_pct, 1)


def _metric(key: str, label: str, score: float | None, description: str, summary: str, components: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "score": round(_clamp(score)) if score is not None else None,
        "description": description,
        "summary": summary,
        "components": components,
    }


def performance_profile(c: sqlite3.Connection, race=None) -> dict[str, Any]:
    """Evidence-informed, transparent 0–100 training profile.

    Scores describe coverage of race-relevant training characteristics. They are
    intentionally not framed as physiological percentages, population percentiles,
    or laboratory measurements. Health metrics are contextual only because their
    absolute values are highly individual.
    """
    today = date.today()
    race_distance = float(race["distance_km"]) if race else 21.0975
    readiness_label, race_floor_km, long_target_km, long_repeat_target = _race_targets(race_distance)
    baseline_setting = max(8.0, min(160.0, float(get_setting(c, "baseline_weekly_km", race_floor_km) or race_floor_km)))
    weekly_target_km = max(race_floor_km, min(race_floor_km * 1.25, baseline_setting))

    weeks = _completed_week_buckets(c, today)
    avg_km = sum(w["km"] for w in weeks) / len(weeks) if weeks else 0.0
    avg_hours = sum(w["seconds"] for w in weeks) / 3600.0 / len(weeks) if weeks else 0.0
    avg_runs = sum(w["runs"] for w in weeks) / len(weeks) if weeks else 0.0
    valid_paces = [float(r["duration_s"]) / float(r["distance_km"]) for r in _recent_runs(c, today) if float(r["distance_km"] or 0) > 0 and float(r["duration_s"] or 0) > 0]
    typical_pace = median(valid_paces) if valid_paces else 360.0
    target_hours = weekly_target_km * typical_pace / 3600.0

    volume_score = _clamp(100.0 * avg_km / weekly_target_km) if weekly_target_km else None
    time_score = _clamp(100.0 * avg_hours / target_hours) if target_hours else None
    easy_eff = _easy_efficiency_trend(c, today)
    efficiency_adjustment = 0.0
    if easy_eff["change_pct"] is not None:
        efficiency_adjustment = max(-8.0, min(8.0, float(easy_eff["change_pct"]) * 1.5))
    aerobic_score = _clamp((0.65 * volume_score + 0.35 * time_score) + efficiency_adjustment) if volume_score is not None and time_score is not None else None
    eff_text = "Easy-Pace/HF: zu wenig Vergleichsdaten"
    if easy_eff["change_pct"] is not None:
        sign = "+" if easy_eff["change_pct"] >= 0 else ""
        eff_text = f"Easy-Pace/HF-Effizienz {sign}{easy_eff['change_pct']:.1f} %"
    aerobic = _metric(
        "aerobic_base",
        "Ausdauerbasis",
        aerobic_score,
        "Umfang und Zeit auf den Beinen über acht abgeschlossene Wochen; Pace/Herzfrequenz bei verknüpften Easy-Läufen wirkt nur als kleiner Trendbonus oder -malus.",
        f"Ø {avg_km:.1f} km / {avg_hours:.1f} h pro Woche · Referenz {weekly_target_km:.1f} km · {eff_text}",
        [
            {"label": "Wochenumfang", "score": round(volume_score) if volume_score is not None else None},
            {"label": "Zeit auf den Beinen", "score": round(time_score) if time_score is not None else None},
        ],
    )

    p5 = base.predict_distance(c, 5.0)
    p10 = base.predict_distance(c, 10.0)
    phm = base.predict_distance(c, 21.0975)
    plan = _plan_adherence(c, today)
    speed_retention, speed_fade = _performance_retention(p5, p10, 5.0, 10.0)
    threshold_retention, threshold_fade = _performance_retention(p10, phm, 10.0, 21.0975)

    speed_score = speed_retention
    if speed_retention is not None and plan["quality_score"] is not None:
        speed_score = 0.80 * speed_retention + 0.20 * float(plan["quality_score"])
    speed_summary = "Noch nicht genug belastbare 5-km-/10-km-Leistungsanker."
    if speed_fade is not None:
        speed_summary = f"5→10 km: {speed_fade:.1f} % zusätzlicher Leistungsabfall ggü. Riegel"
        if plan["quality_total"]:
            speed_summary += f" · {plan['quality_completed']}/{plan['quality_total']} Qualitätsreize absolviert"
    speed = _metric(
        "speed_endurance",
        "Speed-Ausdauer",
        speed_score,
        "Wie gut die kurze Leistungsfähigkeit von 5 km auf 10 km erhalten bleibt. Das ist kein Maß für absolute Höchstgeschwindigkeit.",
        speed_summary,
        [
            {"label": "5→10-km-Erhalt", "score": round(speed_retention) if speed_retention is not None else None},
            {"label": "Qualitätsreize", "score": round(plan["quality_score"]) if plan["quality_score"] is not None else None},
        ],
    )

    threshold_score = threshold_retention
    if threshold_retention is not None and plan["quality_score"] is not None:
        threshold_score = 0.80 * threshold_retention + 0.20 * float(plan["quality_score"])
    if threshold_score is not None and easy_eff["change_pct"] is not None:
        threshold_score = _clamp(threshold_score + max(-4.0, min(4.0, float(easy_eff["change_pct"]))))
    threshold_summary = "Noch nicht genug belastbare 10-km-/HM-Leistungsanker."
    if threshold_fade is not None:
        threshold_summary = f"10 km→HM: {threshold_fade:.1f} % zusätzlicher Leistungsabfall ggü. Riegel"
        if plan["quality_total"]:
            threshold_summary += f" · {plan['quality_completed']}/{plan['quality_total']} Qualitätsreize absolviert"
    threshold = _metric(
        "threshold_endurance",
        "Schwellen-Ausdauer",
        threshold_score,
        "Leistungserhalt von 10 km bis Halbmarathon plus jüngste Qualitätsarbeit. Der Score ist ausdrücklich keine gemessene Laktatschwelle.",
        threshold_summary,
        [
            {"label": "10 km→HM-Erhalt", "score": round(threshold_retention) if threshold_retention is not None else None},
            {"label": "Qualitätsreize", "score": round(plan["quality_score"]) if plan["quality_score"] is not None else None},
        ],
    )

    recent = _recent_runs(c, today)
    longest = max((float(r["distance_km"] or 0) for r in recent), default=0.0)
    long_count = sum(float(r["distance_km"] or 0) >= 0.80 * long_target_km for r in recent)
    long_score = _clamp(100.0 * longest / long_target_km) if long_target_km else None
    repeat_score = _clamp(100.0 * long_count / long_repeat_target) if long_repeat_target else None
    readiness_parts: list[tuple[float, float]] = [(volume_score or 0.0, 0.35), (long_score or 0.0, 0.35), (repeat_score or 0.0, 0.15)]
    if plan["specific_score"] is not None:
        readiness_parts.append((float(plan["specific_score"]), 0.15))
    weight = sum(w for _, w in readiness_parts)
    readiness_score = sum(v * w for v, w in readiness_parts) / weight if weight else None
    readiness_summary = f"Ø {avg_km:.1f} km/Woche · längster Lauf {longest:.1f}/{long_target_km:.0f} km · {long_count} Läufe ≥80 % der Longrun-Referenz"
    if plan["specific_total"]:
        readiness_summary += f" · {plan['specific_completed']}/{plan['specific_total']} spezifische Planreize absolviert"
    readiness = _metric(
        "race_readiness",
        readiness_label,
        readiness_score,
        "Zielspezifische Bereitschaft aus Wochenumfang, Longrun-Länge, wiederholten langen Läufen und – wenn vorhanden – absolvierten langen/Qualitäts-/Race-Prep-Einheiten.",
        readiness_summary,
        [
            {"label": "Wochenumfang", "score": round(volume_score) if volume_score is not None else None},
            {"label": "Längster Lauf", "score": round(long_score) if long_score is not None else None},
            {"label": "Longrun-Wiederholung", "score": round(repeat_score) if repeat_score is not None else None},
            {"label": "Spezifische Planreize", "score": round(plan["specific_score"]) if plan["specific_score"] is not None else None},
        ],
    )

    active_threshold = max(5.0, min(12.0, weekly_target_km * 0.25))
    active_weeks = sum(w["km"] >= active_threshold for w in weeks)
    active_score = 100.0 * active_weeks / len(weeks) if weeks else None
    training_days = get_setting(c, "training_days", [1, 3, 4, 6]) or [1, 3, 4, 6]
    target_runs = max(1, min(7, len(training_days)))
    frequency_score = 100.0 * sum(min(1.0, w["runs"] / target_runs) for w in weeks) / len(weeks) if weeks else None
    continuity_parts: list[tuple[float, float]] = []
    if active_score is not None:
        continuity_parts.append((active_score, 0.40 if plan["score"] is not None else 0.60))
    if frequency_score is not None:
        continuity_parts.append((frequency_score, 0.25 if plan["score"] is not None else 0.40))
    if plan["score"] is not None:
        continuity_parts.append((float(plan["score"]), 0.35))
    weight = sum(w for _, w in continuity_parts)
    continuity_score = sum(v * w for v, w in continuity_parts) / weight if weight else None
    continuity_summary = f"{active_weeks}/{len(weeks)} aktive Wochen · Ø {avg_runs:.1f}/{target_runs} Läufe pro Woche"
    if plan["total"]:
        continuity_summary += f" · {plan['completed']}/{plan['total']} vergangene Planeinheiten absolviert"
    continuity = _metric(
        "training_continuity",
        "Trainingskontinuität",
        continuity_score,
        "Regelmäßigkeit statt bloßer Kilometerzahl: aktive Wochen, Laufhäufigkeit und – bei vorhandener Planung – tatsächlich absolvierte vergangene Einheiten.",
        continuity_summary,
        [
            {"label": "Aktive Wochen", "score": round(active_score) if active_score is not None else None},
            {"label": "Laufhäufigkeit", "score": round(frequency_score) if frequency_score is not None else None},
            {"label": "Planerfüllung", "score": round(plan["score"]) if plan["score"] is not None else None},
        ],
    )

    metrics = [aerobic, speed, threshold, readiness, continuity]
    profile = {
        "profile_version": PROFILE_VERSION,
        "scale_note": "0–100 zeigt die Abdeckung der für dein aktuelles Ziel relevanten Trainingsmerkmale. 100 ist weder dein physiologisches Maximum noch ein Perzentil.",
        "method_note": "Die Gewichte sind transparente, evidenzinformierte Heuristiken aus deinen Lauf- und Plandaten; Health-Werte werden wegen großer individueller Unterschiede nur als Kontext gezeigt.",
        "metrics": metrics,
        "health_context": _health_context(c, today),
        "window_weeks": PROFILE_WINDOW_WEEKS,
        "race_distance_km": race_distance,
        # Legacy numeric keys retained for compatibility with older frontends/coach prompts.
        "Grundlagenausdauer": aerobic["score"],
        "Schwelle": threshold["score"],
        "Speed": speed["score"],
        "Marathon-Ausdauer": readiness["score"],
        "Trainingskonstanz": continuity["score"],
    }
    return profile
