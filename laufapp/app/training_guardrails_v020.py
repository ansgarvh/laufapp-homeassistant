from __future__ import annotations

import json
from datetime import date

from db import get_setting


def enforce_generated_long_run_share(c, workouts: list[dict]) -> list[dict]:
    """Keep Long-Run share as a contextual guardrail, not a universal ceiling.

    The default 45% share is an orientation signal. A marathon Long Run that is
    explicitly supported by recent completed Long-Run history may exceed that
    orientation, including in the current week. A deliberately tighter user
    setting below the normal 45% default remains authoritative for compatibility,
    especially during a mid-week refresh that preserves completed/manual rows.
    """
    if any(w.get("workout_type") == "race" for w in workouts):
        return workouts
    total = sum(float(w.get("distance_km") or 0) for w in workouts)
    if total <= 0:
        return workouts
    cap = max(0.20, min(0.70, float(get_setting(c, "max_long_run_share", 0.45))))
    long_rows = [
        w for w in workouts
        if w.get("workout_type") == "long"
        and w.get("status") == "planned"
        and not int(w.get("manual_override") or 0)
        and str(w.get("modified_by") or "engine") == "engine"
    ]
    if len(long_rows) != 1:
        return workouts
    long_row = long_rows[0]

    row = c.execute("SELECT details_json FROM workouts WHERE id=?", (int(long_row["id"]),)).fetchone()
    try:
        details = json.loads(row["details_json"] or "{}") if row else {}
    except Exception:
        details = {}

    today = date.today().isoformat()
    protected_context = any(
        int(w.get("id") or 0) != int(long_row["id"])
        and (
            w.get("status") != "planned"
            or int(w.get("manual_override") or 0)
            or str(w.get("modified_by") or "engine") != "engine"
            or str(w.get("scheduled_date") or "") < today
        )
        for w in workouts
    )

    # A history-supported peak Long Run is allowed to exceed the normal 45%
    # orientation. If the user has deliberately configured a stricter share
    # (<45%), keep enforcing it. max_long_run_km remains a separate hard ceiling.
    history_supported = bool(details.get("history_supported_share"))
    if history_supported and cap >= 0.445:
        return workouts
    if history_supported and not protected_context:
        return workouts

    long_km = float(long_row.get("distance_km") or 0)
    if long_km / total <= cap + 0.005:
        return workouts
    other = max(0.0, total - long_km)
    if other <= 0 or cap >= 0.999:
        return workouts
    allowed = cap * other / (1.0 - cap)
    if allowed >= long_km - 0.05:
        return workouts
    new_km = round(max(6.0, allowed), 1)
    if new_km >= long_km:
        return workouts

    factor = new_km / max(long_km, 0.001)
    load = details.get("load") or {}
    for key in (
        "distance_km", "duration_min", "low_min", "moderate_min", "high_min",
        "above_lt1_min", "around_lt2_min", "above_lt2_min", "marathon_pace_min",
        "elevation_m", "long_run_duration_min", "score",
    ):
        if key in load:
            load[key] = round(float(load.get(key) or 0) * factor, 2)
    details["load"] = load
    if "mp_km" in details:
        details["mp_km"] = round(float(details.get("mp_km") or 0) * factor, 2)
    previous_why = str(details.get("why") or "").strip()
    guardrail_text = (
        "Die Distanz wurde zusätzlich durch deine eingestellte Longrun-Anteilsgrenze "
        "begrenzt, weil bereits absolvierte, vergangene oder geschützte Einheiten dieser Woche erhalten bleiben."
    )
    details["why"] = f"{previous_why} {guardrail_text}".strip()
    c.execute(
        "UPDATE workouts SET distance_km=?,details_json=? WHERE id=?",
        (new_km, json.dumps(details, ensure_ascii=False), int(long_row["id"])),
    )
    return [
        dict(r) | {"details": _details(r["details_json"]), "pace_text": _pace_text(r)}
        for r in c.execute(
            "SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id",
            (long_row["week_start"],),
        ).fetchall()
    ]


def _details(raw: str) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _pace_text(row) -> str:
    lo = row["pace_low_s_per_km"]
    hi = row["pace_high_s_per_km"]
    if lo is None or hi is None:
        return "nach RPE"
    def fmt(v):
        v = int(round(float(v)))
        return f"{v//60}:{v%60:02d}"
    return f"{fmt(lo)}–{fmt(hi)} min/km"
