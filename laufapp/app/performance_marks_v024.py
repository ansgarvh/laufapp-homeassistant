"""Performance-anchor improvements for Laufapp v0.2.4.

The legacy stack already stores manual performance marks, but Apple Health runs
were not promoted to durable performance anchors and normal run evidence was
weighted too weakly to demonstrate improvement after a confirmed PB.  This
module installs additive, schema-free behavior on top of the tested v0.2.3
stack.
"""

from __future__ import annotations

import calendar
import math
from datetime import date, timedelta
from typing import Any

AUTO_SOURCE = "apple_health_best"
CONFIRMED_SOURCES = {"manual", "race", "time_trial", AUTO_SOURCE}


def months_ago(months: int = 24, ref: date | None = None) -> date:
    ref = ref or date.today()
    raw = ref.year * 12 + ref.month - 1 - months
    year, month0 = divmod(raw, 12)
    month = month0 + 1
    day = min(ref.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _quality(source: str) -> float:
    if source in {"manual", "race", "time_trial"}:
        return 1.0
    if source == AUTO_SOURCE:
        return 0.92
    return 0.55


def detect_apple_health_best_efforts(c, training, months: int = 24) -> list[dict[str, Any]]:
    """Return best near-standard-distance Apple Health efforts in the period.

    We deliberately only accept workouts very close to the standard distance.
    Without cumulative-distance samples a 30 km workout must not be treated as a
    measured half-marathon split.  Small GPS/watch distance deviations are
    normalized with the same Riegel model used by the existing prediction
    engine.
    """
    cutoff = months_ago(months).isoformat()
    runs = c.execute(
        "SELECT started_at,distance_km,duration_s,source FROM runs "
        "WHERE substr(started_at,1,10)>=? AND duration_s>0 "
        "AND source LIKE 'apple_health%'",
        (cutoff,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for target in training.STANDARD_DISTANCES:
        candidates = []
        for r in runs:
            km = float(r["distance_km"] or 0)
            duration = float(r["duration_s"] or 0)
            if km <= 0 or duration <= 0 or not (target * 0.98 <= km <= target * 1.03):
                continue
            normalized = training.riegel(duration, km, target)
            candidates.append((normalized, km, duration, str(r["started_at"])[:10]))
        if not candidates:
            continue
        normalized, km, duration, mark_date = min(candidates, key=lambda x: x[0])
        out.append(
            {
                "distance_km": float(target),
                "duration_s": float(normalized),
                "raw_distance_km": km,
                "raw_duration_s": duration,
                "date": mark_date,
                "source": AUTO_SOURCE,
                "label": f"Apple Health · {training.LABELS.get(target, f'{target:g} km')}",
                "quality": _quality(AUTO_SOURCE),
            }
        )
    return out


def sync_apple_health_best_marks(c, training, months: int = 24) -> int:
    """Refresh only auto-generated marks; never modify user-entered PBs."""
    detected = detect_apple_health_best_efforts(c, training, months)
    c.execute("DELETE FROM performance_marks WHERE source=?", (AUTO_SOURCE,))
    for mark in detected:
        c.execute(
            "INSERT INTO performance_marks(distance_km,duration_s,mark_date,source,label) "
            "VALUES(?,?,?,?,?)",
            (
                mark["distance_km"],
                mark["duration_s"],
                mark["date"],
                AUTO_SOURCE,
                mark["label"],
            ),
        )
    return len(detected)


def anchors_v024(c, training) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    cutoff = months_ago(24).isoformat()
    for r in c.execute(
        "SELECT * FROM performance_marks WHERE mark_date>=? ORDER BY mark_date DESC",
        (cutoff,),
    ).fetchall():
        source = str(r["source"] or "manual")
        out.append(
            {
                "distance_km": float(r["distance_km"]),
                "duration_s": float(r["duration_s"]),
                "date": r["mark_date"],
                "source": source,
                "label": r["label"] or "Leistungsmarke",
                "quality": _quality(source),
            }
        )

    # Existing installations immediately benefit even before the next import.
    # Avoid duplicate auto anchors when a synchronized DB row is already present.
    synced_targets = {
        round(float(x["distance_km"]), 4)
        for x in out
        if x["source"] == AUTO_SOURCE
    }
    for mark in detect_apple_health_best_efforts(c, training, 24):
        if round(float(mark["distance_km"]), 4) not in synced_targets:
            out.append(mark)

    # Recent training remains lower-confidence evidence, but it is no longer
    # excluded merely because a confirmed race result exists.
    recent_cutoff = (date.today() - timedelta(days=210)).isoformat()
    runs = [
        dict(r)
        for r in c.execute(
            "SELECT started_at,distance_km,duration_s FROM runs "
            "WHERE started_at>=? AND distance_km>=4.5 AND duration_s>0",
            (recent_cutoff,),
        ).fetchall()
    ]
    for target in training.STANDARD_DISTANCES:
        eligible = [
            r
            for r in runs
            if 0.85 * target <= float(r["distance_km"]) <= 1.35 * target
        ]
        if eligible:
            best = min(
                eligible,
                key=lambda r: float(r["duration_s"]) / float(r["distance_km"]),
            )
            out.append(
                {
                    "distance_km": float(best["distance_km"]),
                    "duration_s": float(best["duration_s"]),
                    "date": best["started_at"][:10],
                    "source": "training",
                    "label": "Schneller Trainingslauf",
                    "quality": _quality("training"),
                }
            )
    return out


def predict_distance_v024(c, target: float, training) -> dict[str, Any] | None:
    anchors = anchors_v024(c, training)
    if not anchors:
        return None

    evidence = []
    for a in anchors:
        exp = 1.075 if target >= 42 and a["distance_km"] < 20 else 1.06
        predicted = training.riegel(a["duration_s"], a["distance_km"], target, exp)
        extrap = abs(math.log(max(target / a["distance_km"], 1e-9), 2))
        age = max(0, (date.today() - date.fromisoformat(a["date"][:10])).days)
        # A confirmed PB remains meaningful for the full 24-month import window.
        recency = max(0.65, 1 - age / 900)
        score = a["quality"] * recency / (1 + 0.28 * extrap)
        evidence.append({**a, "predicted": predicted, "score": score})

    evidence.sort(key=lambda x: (-x["score"], x["predicted"]))
    top_score = evidence[0]["score"]
    eligible = [p for p in evidence if p["score"] >= top_score * 0.60]
    selected = min(eligible, key=lambda x: x["predicted"])

    confirmed = [p for p in evidence if p["source"] in CONFIRMED_SOURCES]
    best_confirmed = min(confirmed, key=lambda x: x["predicted"]) if confirmed else None

    base_pred = selected["predicted"]
    # Confirmed PB = hard capability anchor.  Faster recent evidence may improve
    # the estimate, but a single lower-confidence training run is blended rather
    # than replacing the race result outright.
    if best_confirmed:
        confirmed_pred = best_confirmed["predicted"]
        if selected["source"] == "training" and base_pred < confirmed_pred:
            base_pred = 0.70 * base_pred + 0.30 * confirmed_pred
            base_pred = max(base_pred, confirmed_pred * 0.92)
        else:
            base_pred = min(base_pred, confirmed_pred)

    avg = sum(training.weekly_volume(c, 6)) / 6
    longest = max(training.recent_long_runs(c) or [0])
    penalty = 1.0
    notes: list[str] = []
    if target >= 40 and selected["distance_km"] < 35:
        if avg < 30:
            penalty *= 1.07
            notes.append("geringer jüngster Wochenumfang")
        elif avg < 40:
            penalty *= 1.045
            notes.append("moderater Wochenumfang")
        elif avg < 50:
            penalty *= 1.02
        if longest < 24:
            penalty *= 1.045
            notes.append("noch wenig lange Läufe")
        elif longest < 28:
            penalty *= 1.02
    elif target >= 20 and selected["distance_km"] < 18 and avg < 25:
        penalty *= 1.035

    pred = base_pred * penalty
    # For non-marathon distances a recent confirmed PB must not be made slower
    # by generic readiness penalties. Marathon-specific endurance penalties stay.
    if best_confirmed and target < 40:
        pred = min(pred, best_confirmed["predicted"])

    conf = max(0.35, min(0.96, selected["score"] * (0.95 if penalty == 1 else 0.88)))
    unc = 0.02 + (1 - conf) * 0.09
    low, high = pred * (1 - unc), pred * (1 + unc)
    improvement = None
    if best_confirmed:
        improvement = round(best_confirmed["predicted"] - pred)

    return {
        "distance_km": target,
        "label": training.LABELS.get(target, f"{target:g} km"),
        "predicted_seconds": round(pred),
        "predicted_time": training.hms(pred),
        "low_seconds": round(low),
        "high_seconds": round(high),
        "range_text": f"{training.hms(low)}–{training.hms(high)}",
        "confidence": round(conf, 2),
        "anchor": {k: selected[k] for k in ("distance_km", "duration_s", "date", "source", "label")},
        "performance_anchor": (
            {k: best_confirmed[k] for k in ("distance_km", "duration_s", "date", "source", "label")}
            if best_confirmed
            else None
        ),
        "improvement_since_best_seconds": improvement,
        "notes": notes,
    }


def install(training, health_import, import_jobs) -> None:
    """Install patches once on the live compatibility stack."""
    if getattr(training, "_v024_performance_installed", False):
        return
    original_import = health_import.import_apple_health

    def import_with_best_marks(c, path, months=24, progress=None):
        result = original_import(c, path, months=months, progress=progress)
        detected = sync_apple_health_best_marks(c, training, months)
        result["performance_marks_detected"] = detected
        return result

    def patched_anchors(c):
        return anchors_v024(c, training)

    def patched_predict(c, target):
        return predict_distance_v024(c, target, training)

    training._anchors = patched_anchors
    training.predict_distance = patched_predict
    health_import.import_apple_health = import_with_best_marks
    import_jobs.import_apple_health = import_with_best_marks
    training._v024_performance_installed = True
