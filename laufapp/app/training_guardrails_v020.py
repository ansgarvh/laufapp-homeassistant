from __future__ import annotations

import json
from datetime import date

import training as base
import training_v020 as orchestration
from db import get_setting
from training_runtime_refinements_v020 import apply_runtime_refinements

# main_v020 imports this module only after training_v020 is loaded. Apply the
# calendar/fixed-distance refinements before main_v020 captures generate_week.
apply_runtime_refinements(orchestration)


_LOAD_KEYS = (
    "distance_km", "duration_min", "low_min", "moderate_min", "high_min",
    "above_lt1_min", "around_lt2_min", "above_lt2_min", "marathon_pace_min",
    "elevation_m", "long_run_duration_min", "score",
)


def _scale_load(details: dict, factor: float) -> dict:
    load = details.get("load") or {}
    for key in _LOAD_KEYS:
        if key in load:
            load[key] = round(float(load.get(key) or 0) * factor, 2)
    details["load"] = load
    return details


def _redistribute_trimmed_longrun_km(c, workouts: list[dict], freed_km: float, target_total: float) -> float:
    """Move guardrail-trimmed distance only into flexible future Easy runs.

    A Long-Run share guardrail must not silently turn a 63 km weekly target into
    a 58 km week. When the rest of the week is still engine-owned, the removed
    distance is redistributed as low-intensity volume. Protected/manual/past
    workouts are never changed. If no flexible Easy run remains, the shortfall is
    left in place rather than mutating user-owned training.
    """
    if freed_km <= 0.05:
        return 0.0
    today = date.today().isoformat()
    current_total = sum(float(w.get("distance_km") or 0) for w in workouts) - freed_km
    refill = min(freed_km, max(0.0, float(target_total) - current_total))
    if refill <= 0.05:
        return 0.0

    flexible = [
        w for w in workouts
        if w.get("workout_type") == "easy"
        and w.get("status") == "planned"
        and not int(w.get("manual_override") or 0)
        and str(w.get("modified_by") or "engine") == "engine"
        and str(w.get("scheduled_date") or "") >= today
    ]
    if not flexible:
        return 0.0

    weights = [max(1.0, float(w.get("distance_km") or 0)) for w in flexible]
    weight_sum = sum(weights)
    distributed = 0.0
    for index, (workout, weight) in enumerate(zip(flexible, weights)):
        share = refill - distributed if index == len(flexible) - 1 else refill * weight / weight_sum
        if share <= 0:
            continue
        row = c.execute("SELECT distance_km,details_json FROM workouts WHERE id=?", (int(workout["id"]),)).fetchone()
        if not row:
            continue
        old_km = float(row["distance_km"] or 0)
        new_km = round(old_km + share, 1)
        actual_add = max(0.0, new_km - old_km)
        if actual_add <= 0:
            continue
        try:
            details = json.loads(row["details_json"] or "{}")
        except Exception:
            details = {}
        details = _scale_load(details, new_km / max(old_km, 0.001))
        details["guardrail_redistributed_km"] = round(actual_add, 2)
        c.execute(
            "UPDATE workouts SET distance_km=?,details_json=? WHERE id=?",
            (new_km, json.dumps(details, ensure_ascii=False), int(workout["id"])),
        )
        distributed += actual_add
    return round(distributed, 2)


def enforce_generated_long_run_share(c, workouts: list[dict]) -> list[dict]:
    """Keep Long-Run share as a contextual guardrail, not a universal ceiling.

    The default 45% share is an orientation signal. A fully engine-generated
    future week is therefore not post-hoc shortened merely to hit exactly 45%;
    the LongRunPlanner already controls the normal share and recent tolerated
    history may justify a higher value. A deliberately tighter user setting below
    the normal 45% default remains authoritative. In mixed/protected weeks the
    guardrail may still trim the generated Long Run, but removed kilometres are
    shifted to flexible Easy runs where possible so the weekly target is not lost.
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

    long_km = float(long_row.get("distance_km") or 0)
    week_ref = date.fromisoformat(str(long_row["week_start"]))
    history = base.long_run_history(c, week_ref)
    longest_recent = max(float(history.get("longest_4w") or 0), float(history.get("longest_8w") or 0))
    phase = str(details.get("phase") or "")
    max_long = float(get_setting(c, "max_long_run_km", 35.0))
    inferred_history_supported = (
        phase in {"build", "specific"}
        and longest_recent >= 24.0
        and long_km <= max_long + 0.05
        and long_km <= longest_recent + 3.0
    )
    history_supported = bool(details.get("history_supported_share")) or inferred_history_supported

    # The default 45% value is an orientation for a clean, fully generated week,
    # not a second hard cap after the planner has already assembled the week.
    # A stricter (<45%) legacy/user value remains binding. Protected mixed weeks
    # still receive the contextual check because their composition can change
    # independently of the newly generated Long Run.
    if cap >= 0.445 and not protected_context:
        return workouts
    if history_supported and cap >= 0.445:
        return workouts

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
    details = _scale_load(details, factor)
    if "mp_km" in details:
        details["mp_km"] = round(float(details.get("mp_km") or 0) * factor, 2)
    previous_why = str(details.get("why") or "").strip()
    guardrail_text = (
        "Die Longrun-Distanz wurde durch die wirksame Anteilsgrenze begrenzt. "
        "Soweit möglich wird das entfernte Wochenbudget ausschließlich auf lockere, "
        "noch automatisch geplante Einheiten verteilt."
    )
    details["why"] = f"{previous_why} {guardrail_text}".strip()
    c.execute(
        "UPDATE workouts SET distance_km=?,details_json=? WHERE id=?",
        (new_km, json.dumps(details, ensure_ascii=False), int(long_row["id"])),
    )

    target_total = float(details.get("week_target_km") or total)
    _redistribute_trimmed_longrun_km(c, workouts, long_km - new_km, min(total, target_total))
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
