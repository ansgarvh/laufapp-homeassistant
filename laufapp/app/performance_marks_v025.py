"""Conservative post-PB progression model for Laufapp v0.2.5.

The confirmed best time remains the capability anchor. A prediction may move
faster only when the database contains sustained training after that mark. The
progression adjustment is deliberately capped and uses training consistency,
weekly-volume development and long-run development; it never invents a faster
race result from elapsed time alone.
"""

from __future__ import annotations

from datetime import date, timedelta
from statistics import mean
from typing import Any


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _weekly_km(c, start: date, end: date) -> list[float]:
    rows = c.execute(
        "SELECT substr(started_at,1,10) AS d,distance_km FROM runs "
        "WHERE substr(started_at,1,10)>=? AND substr(started_at,1,10)<? AND duration_s>0",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    weeks: dict[date, float] = {}
    cursor = _week_start(start)
    while cursor < end:
        weeks[cursor] = 0.0
        cursor += timedelta(days=7)
    for row in rows:
        d = date.fromisoformat(str(row["d"]))
        ws = _week_start(d)
        if ws in weeks:
            weeks[ws] += float(row["distance_km"] or 0)
    return [weeks[k] for k in sorted(weeks)]


def _longest(c, start: date, end: date) -> float:
    row = c.execute(
        "SELECT MAX(distance_km) AS km FROM runs WHERE substr(started_at,1,10)>=? "
        "AND substr(started_at,1,10)<? AND duration_s>0",
        (start.isoformat(), end.isoformat()),
    ).fetchone()
    return float(row["km"] or 0.0)


def progression_signal(c, performance_anchor: dict[str, Any] | None, ref: date | None = None) -> dict[str, Any]:
    """Estimate a bounded training-development signal since a confirmed PB.

    This is not a race-time model by itself. It is only an evidence modifier for
    the existing prediction and requires at least eight weeks after the PB.
    """
    ref = ref or date.today()
    if not performance_anchor or not performance_anchor.get("date"):
        return {"eligible": False, "reason": "no_confirmed_anchor", "adjustment": 0.0}
    anchor_date = date.fromisoformat(str(performance_anchor["date"])[:10])
    elapsed = (ref - anchor_date).days
    if elapsed < 56:
        return {"eligible": False, "reason": "too_recent", "adjustment": 0.0, "days": elapsed}

    current_start = _week_start(ref) - timedelta(weeks=8)
    current_end = _week_start(ref)
    pre_end = _week_start(anchor_date)
    pre_start = pre_end - timedelta(weeks=8)
    current = _weekly_km(c, current_start, current_end)
    previous = _weekly_km(c, pre_start, pre_end)
    if not current:
        return {"eligible": False, "reason": "no_recent_training", "adjustment": 0.0}

    active_fraction = sum(1 for km in current if km >= 10.0) / len(current)
    current_avg = mean(current)
    previous_nonzero = [km for km in previous if km > 0]
    previous_avg = mean(previous_nonzero) if previous_nonzero else 0.0
    if active_fraction < 0.75 or current_avg < 20.0:
        return {
            "eligible": False,
            "reason": "insufficient_consistency",
            "adjustment": 0.0,
            "active_week_fraction": round(active_fraction, 2),
            "current_weekly_km": round(current_avg, 1),
        }

    months = min(1.0, elapsed / 120.0)
    consistency_bonus = 0.006 * months * min(1.0, active_fraction / 0.875)

    volume_ratio = current_avg / previous_avg if previous_avg >= 15.0 else 1.0
    volume_bonus = max(0.0, min(0.015, (volume_ratio - 1.0) * 0.06))

    current_long = _longest(c, current_start, current_end)
    previous_long = _longest(c, pre_start, pre_end)
    long_ratio = current_long / previous_long if previous_long >= 8.0 else 1.0
    long_bonus = max(0.0, min(0.005, (long_ratio - 1.0) * 0.02))

    adjustment = min(0.025, consistency_bonus + volume_bonus + long_bonus)
    return {
        "eligible": adjustment > 0,
        "reason": "sustained_training" if adjustment > 0 else "no_positive_progression_signal",
        "adjustment": round(adjustment, 5),
        "active_week_fraction": round(active_fraction, 2),
        "current_weekly_km": round(current_avg, 1),
        "pre_pb_weekly_km": round(previous_avg, 1),
        "volume_ratio": round(volume_ratio, 3),
        "current_longest_km": round(current_long, 1),
        "pre_pb_longest_km": round(previous_long, 1),
        "days_since_pb": elapsed,
    }


def install(training, previous_module) -> None:
    """Wrap the v0.2.4 predictor without changing its anchor safeguards."""
    if getattr(training, "_v025_progression_installed", False):
        return
    original_predict = training.predict_distance

    def predict_with_progression(c, target):
        result = original_predict(c, target)
        if not result or float(target) >= 40:
            return result
        anchor = result.get("performance_anchor")
        signal = progression_signal(c, anchor)
        result["progression_signal"] = signal
        if not signal.get("eligible") or not anchor:
            return result

        anchor_pred = previous_module.riegel(
            float(anchor["duration_s"]), float(anchor["distance_km"]), float(target), 1.06
        )
        current = float(result["predicted_seconds"])
        progression_pred = anchor_pred * (1.0 - float(signal["adjustment"]))

        # Never make an already-faster evidence-based estimate slower. The
        # progression signal only helps when v0.2.4 is effectively pinned to PB.
        new_pred = min(current, progression_pred)
        if new_pred >= current - 1:
            return result

        result["predicted_seconds"] = round(new_pred)
        result["predicted_time"] = previous_module.hms(new_pred)
        conf = float(result.get("confidence") or 0.5)
        unc = 0.02 + (1 - conf) * 0.09
        result["low_seconds"] = round(new_pred * (1 - unc))
        result["high_seconds"] = round(new_pred * (1 + unc))
        result["range_text"] = f"{previous_module.hms(result['low_seconds'])}–{previous_module.hms(result['high_seconds'])}"
        result["improvement_since_best_seconds"] = round(anchor_pred - new_pred)
        notes = list(result.get("notes") or [])
        notes.append("kontinuierliche Trainingsentwicklung seit Bestzeit")
        result["notes"] = notes
        return result

    training.predict_distance = predict_with_progression
    training._v025_progression_installed = True
