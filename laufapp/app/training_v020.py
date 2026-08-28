from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import training as base
from db import get_setting, set_setting

VERSION = "0.2.0"


def _priority_map(c) -> dict[str, str]:
    raw = get_setting(c, "race_priorities", {}) or {}
    return {str(k): ("B" if str(v).upper() == "B" else "A") for k, v in dict(raw).items()}


def race_priority(c, race_id: int) -> str:
    return _priority_map(c).get(str(int(race_id)), "A")


def current_race(c, ref: date | None = None):
    """Return the next enabled A-race from ref onward.

    Older installations have no explicit race type. They are intentionally
    treated as A-races so an upgrade never loses the existing plan focus.
    """
    ref = ref or date.today()
    priorities = _priority_map(c)
    for r in c.execute(
        "SELECT * FROM races WHERE active=1 AND race_date>=? ORDER BY race_date,id",
        (ref.isoformat(),),
    ).fetchall():
        if priorities.get(str(int(r["id"])), "A") == "A":
            return r
    return None


def race_for_week(c, ws: date):
    """A-race governing a given plan week.

    This allows several A-races in one season: before the first A-race the
    first one is the focus, and after it the next future A-race takes over.
    """
    priorities = _priority_map(c)
    for r in c.execute(
        "SELECT * FROM races WHERE active=1 AND race_date>=? ORDER BY race_date,id",
        (ws.isoformat(),),
    ).fetchall():
        if priorities.get(str(int(r["id"])), "A") == "A":
            return r
    return None


def b_races_for_week(c, ws: date):
    end = ws + timedelta(days=6)
    priorities = _priority_map(c)
    return [
        r
        for r in c.execute(
            "SELECT * FROM races WHERE active=1 AND race_date BETWEEN ? AND ? ORDER BY race_date,id",
            (ws.isoformat(), end.isoformat()),
        ).fetchall()
        if priorities.get(str(int(r["id"])), "A") == "B"
    ]


def _phase(race, ws: date):
    return base._phase(race, ws)


def _block_state(race, ws: date, phase: str) -> dict:
    weeks = max(0, (date.fromisoformat(race["race_date"]) - ws).days // 7)
    if phase == "build":
        cycle = 4
        rem = weeks % cycle
        return {"cycle": cycle, "position": 0 if rem == 0 else cycle - rem, "recovery": rem == 0}
    if phase == "specific":
        cycle = 3
        rem = weeks % cycle
        return {"cycle": cycle, "position": 0 if rem == 0 else cycle - rem, "recovery": rem == 0}
    return {"cycle": None, "position": None, "recovery": False}


def _weekly_target(c, race, ws: date):
    prefs = base._prefs(c, float(race["distance_km"]))
    ev = base.established_volume(c, ws)
    established = ev["km"] or prefs["baseline"]
    phase, weeks = _phase(race, ws)
    block = _block_state(race, ws, phase)

    step = {"gradual": 0.0125, "steady": 0.020, "progressive": 0.030}.get(
        prefs["volume"], 0.020
    )

    if block["recovery"]:
        factor = 0.84
        phase = "recovery"
    elif phase == "build":
        factor = 1.0 + step * max(1, int(block["position"] or 1))
    elif phase == "specific":
        factor = 1.0 + (step + 0.008) * max(1, int(block["position"] or 1))
    elif phase == "peak":
        peak_position = max(1, min(3, 6 - weeks))
        peak_step = {"gradual": 0.018, "steady": 0.025, "progressive": 0.032}.get(
            prefs["volume"], 0.025
        )
        factor = 1.0 + peak_step * peak_position
    elif phase == "taper":
        factor = {2: 0.72, 1: 0.52}.get(weeks, 0.45)
    elif phase == "race":
        factor = 0.42
    else:
        factor = 1.0

    if ev["trend"] == "reduziert" and phase not in {"taper", "race", "recovery"}:
        factor = min(factor, 0.96)

    # Historic caps remain guardrails, but established runners are never forced
    # below their proven recent load by an arbitrary default ceiling.
    dist = float(race["distance_km"])
    ceiling = 82 if dist >= 40 else 66 if dist >= 20 else 54
    ceiling = max(ceiling, established * 1.04)
    target = max(14.0, min(ceiling, established * factor))

    recommendation = automatic_max_weekly_km(c, race, ws)
    user_cap = (
        float(get_setting(c, "max_weekly_km", recommendation))
        if get_setting(c, "max_weekly_km_mode", "auto") == "user"
        else recommendation
    )
    return min(target, user_cap), phase


def automatic_max_weekly_km(c, race=None, ref: date | None = None):
    race = race or current_race(c, ref)
    dist = float(race["distance_km"]) if race else 21.0975
    ev = base.established_volume(c, ref)
    established = ev["km"] or float(get_setting(c, "baseline_weekly_km", 40))
    factor = 1.12 if dist >= 40 else 1.09 if dist >= 20 else 1.07
    if ev["trend"] == "reduziert":
        factor *= 0.95
    return round(max(14, min(180, established * factor)), 1)


def _week_templates(c, race, ws: date, phase: str, total: float):
    """Return preferred dates/templates plus B-race metadata.

    A B-race only replaces the Long Run of its own week. The normal quality and
    easy sessions are kept unchanged. If the race itself lands on another
    configured training day, that workout is moved to the freed Long Run day so
    the intervention stays local to the race weekend.
    """
    templates = list(base._templates(c, race, ws, phase, total))
    days = sorted(
        set(
            int(x)
            for x in get_setting(c, "training_days", [1, 3, 4, 6])
            if 0 <= int(x) <= 6
        )
    )
    days = days if 3 <= len(days) <= 7 else [1, 3, 4, 6]
    dates = [ws + timedelta(days=d) for d in days]
    zones = dict(base._zones(c, race))
    equivalent_by_title: dict[str, float] = {}
    b_meta = None

    b_races = b_races_for_week(c, ws)
    if not b_races or phase == "race":
        return dates, templates, zones, equivalent_by_title, b_meta

    # API validation prevents several B-races in one week. If legacy/manual DB
    # edits still created more than one, only the earliest is applied and the
    # week guardrail can surface the unusual density instead of corrupting data.
    b = b_races[0]
    long_idx = next((i for i, t in enumerate(templates) if t[0] == "long"), None)
    if long_idx is None:
        return dates, templates, zones, equivalent_by_title, b_meta

    original_long = float(templates[long_idx][2])
    original_long_date = dates[long_idx]
    race_day = date.fromisoformat(b["race_date"])

    collision_idx = next(
        (i for i, d in enumerate(dates) if i != long_idx and d == race_day), None
    )
    if collision_idx is not None:
        dates[collision_idx] = original_long_date
    dates[long_idx] = race_day

    title = f"B-Rennen · {b['name']}"
    goal_pace = float(b["goal_seconds"]) / float(b["distance_km"])
    zones["b_race"] = (goal_pace - 5, goal_pace + 5)
    templates[long_idx] = (
        "race",
        title,
        float(b["distance_km"]),
        "b_race",
        "Wettkampf",
        "B-Rennen",
        "B-Rennen ersetzt nur den Longrun dieser Woche; der übrige Trainingsblock bleibt unverändert.",
    )
    equivalent_by_title[title] = original_long
    b_meta = {
        "id": int(b["id"]),
        "name": b["name"],
        "race_date": b["race_date"],
        "distance_km": float(b["distance_km"]),
        "goal_seconds": int(b["goal_seconds"]),
        "replaced_long_run_km": round(original_long, 1),
    }
    return dates, templates, zones, equivalent_by_title, b_meta


def plan_basis(c, ws, race, total, phase):
    ev = base.established_volume(c, ws)
    lh = base.long_run_history(c, ws)
    weeks = max(0, (date.fromisoformat(race["race_date"]) - ws).days // 7)
    block = _block_state(race, ws, base._phase(race, ws)[0])
    b = b_races_for_week(c, ws)
    return {
        "established_weekly_km": ev["km"]
        or base._prefs(c, float(race["distance_km"]))["baseline"],
        "trend": ev["trend"],
        "longest_recent_km": lh["longest_8w"],
        "phase": phase,
        "weeks_to_race": weeks,
        "planned_weekly_km": round(total, 1),
        "current_partial_km": ev["current_partial_km"],
        "focus_race_id": int(race["id"]),
        "focus_race_name": race["name"],
        "block_position": block["position"],
        "block_cycle": block["cycle"],
        "b_race": (
            {"id": int(b[0]["id"]), "name": b[0]["name"], "race_date": b[0]["race_date"]}
            if b
            else None
        ),
    }


def generate_week(c, ws: date | None = None, force=False):
    ws = base.week_start_for(ws or date.today())
    key = ws.isoformat()
    removed = base._cleanup_generated_collisions(c, ws)
    existing = c.execute(
        "SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id", (key,)
    ).fetchall()
    native = c.execute(
        "SELECT * FROM workouts WHERE origin_week_start=? ORDER BY scheduled_date,id", (key,)
    ).fetchall()
    if native and not force and not removed:
        return [base._wdict(r) for r in existing]

    race = race_for_week(c, ws)
    if not race:
        return [base._wdict(r) for r in existing]

    if force:
        c.execute(
            "DELETE FROM workouts WHERE origin_week_start=? AND scheduled_date>=? "
            "AND status='planned' AND linked_run_id IS NULL AND COALESCE(manual_override,0)=0",
            (key, date.today().isoformat()),
        )
        c.execute("DELETE FROM plan_reviews WHERE week_start=?", (key,))

    native_rows = c.execute(
        "SELECT * FROM workouts WHERE origin_week_start=? ORDER BY scheduled_date,id", (key,)
    ).fetchall()
    total, phase = _weekly_target(c, race, ws)
    dates, templates, zones, equivalent_by_title, b_meta = _week_templates(
        c, race, ws, phase, total
    )

    remaining_slots = base._remaining_template_slots(dates, templates, native_rows)
    visible = c.execute(
        "SELECT * FROM workouts WHERE scheduled_date BETWEEN ? AND ? ORDER BY scheduled_date,id",
        (key, (ws + timedelta(days=6)).isoformat()),
    ).fetchall()
    occupied = {r["scheduled_date"] for r in visible}
    preserved_km = sum(float(r["distance_km"] or 0) for r in visible)
    candidates = base._schedule_remaining_slots(ws, remaining_slots, occupied)

    # B-race distance itself is fixed. For scaling calculations it carries the
    # distance of the Long Run it replaced, keeping all other sessions unchanged
    # in a normal clean week.
    equivalent_candidate_km = sum(
        float(equivalent_by_title.get(t[1], t[2])) for _, t in candidates
    )
    remaining_km = max(0.0, total - preserved_km)
    scale = (
        min(1.0, remaining_km / equivalent_candidate_km)
        if equivalent_candidate_km > 0
        else 0.0
    )

    generation = datetime.now(timezone.utc).isoformat()
    for scheduled, t in candidates:
        typ, title, km, zone, rpe, purpose, instructions = t
        fixed_b_race = title in equivalent_by_title
        effective_km = float(km) if fixed_b_race else float(km) * scale
        if effective_km <= 0.05:
            continue
        low, high = zones.get(zone, (None, None))
        details = {
            "purpose": purpose,
            "instructions": instructions,
            "phase": phase,
            "week_target_km": round(total, 1),
            "rpe_target": rpe,
            "plan_basis": plan_basis(c, ws, race, total, phase),
        }
        if typ == "race":
            if fixed_b_race and b_meta:
                details.update(
                    {
                        "race_id": b_meta["id"],
                        "race_priority": "B",
                        "goal_seconds": b_meta["goal_seconds"],
                        "replaced_long_run_km": b_meta["replaced_long_run_km"],
                    }
                )
            else:
                details.update(
                    {
                        "race_id": int(race["id"]),
                        "race_priority": "A",
                        "goal_seconds": int(race["goal_seconds"]),
                    }
                )
        c.execute(
            "INSERT INTO workouts(week_start,origin_week_start,scheduled_date,workout_type,title,distance_km,"
            "pace_low_s_per_km,pace_high_s_per_km,details_json,status,manual_override,modified_by,"
            "generation_version,plan_generation_id) VALUES(?,?,?,?,?,?,?,?,?,'planned',0,'engine',?,?)",
            (
                key,
                key,
                scheduled.isoformat(),
                typ,
                title,
                round(effective_km, 1),
                low,
                high,
                json.dumps(details, ensure_ascii=False),
                VERSION,
                generation,
            ),
        )

    if force:
        set_setting(c, "plan_stale", False)
        set_setting(c, "plan_stale_reason", "")
    return [
        base._wdict(r)
        for r in c.execute(
            "SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id", (key,)
        ).fetchall()
    ]


def refresh_plan(c, start: date | None = None, weeks=4):
    start = base.week_start_for(start or date.today())
    old = []
    for i in range(weeks):
        ws = start + timedelta(days=7 * i)
        base._cleanup_generated_collisions(c, ws)
        rows0 = [
            base._wdict(r)
            for r in c.execute(
                "SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id",
                (ws.isoformat(),),
            )
        ]
        if i == 0:
            old = rows0
        generate_week(c, ws, True)
    new = [
        base._wdict(r)
        for r in c.execute(
            "SELECT * FROM workouts WHERE week_start=? ORDER BY scheduled_date,id",
            (start.isoformat(),),
        )
    ]

    def stats(xs):
        return (
            round(sum(float(x["distance_km"]) for x in xs), 1),
            max(
                [
                    float(x["distance_km"])
                    for x in xs
                    if x["workout_type"] in {"long", "race"}
                ]
                or [0]
            ),
            next((x["title"] for x in xs if x["workout_type"] == "quality"), None),
        )

    a, b = stats(old), stats(new)
    diff = {}
    if a[0] != b[0]:
        diff["volume_km"] = {"old": a[0], "new": b[0]}
    if a[1] != b[1]:
        diff["long_run_km"] = {"old": a[1], "new": b[1]}
    if a[2] != b[2]:
        diff["quality"] = {"old": a[2], "new": b[2]}
    if len(old) != len(new):
        diff["session_count"] = {"old": len(old), "new": len(new)}
    return {
        "updated": bool(diff),
        "diff": diff,
        "weeks": weeks,
        "summary_week_start": start.isoformat(),
    }


def week_summary(c, ws):
    workouts = generate_week(c, ws)
    planned = sum(float(w["distance_km"]) for w in workouts)
    race = race_for_week(c, ws)
    total, phase = _weekly_target(c, race, ws) if race else (planned, "build")
    basis = plan_basis(c, ws, race, total, phase) if race else None
    actual = float(
        c.execute(
            "SELECT COALESCE(SUM(distance_km),0) km FROM runs WHERE started_at>=? AND started_at<?",
            (ws.isoformat(), (ws + timedelta(days=7)).isoformat()),
        ).fetchone()["km"]
        or 0
    )
    return {
        "week_start": ws.isoformat(),
        "week_end": (ws + timedelta(days=6)).isoformat(),
        "workouts": workouts,
        "planned_km": round(planned, 1),
        "completed_planned_km": round(
            sum(float(w["distance_km"]) for w in workouts if w["status"] == "completed"),
            1,
        ),
        "actual_km": round(actual, 1),
        "guardrails": base.guardrails(c, workouts),
        "plan_basis": basis,
        "plan_stale": bool(get_setting(c, "plan_stale", False)),
        "plan_stale_reason": get_setting(c, "plan_stale_reason", ""),
    }


def dashboard(c):
    race = current_race(c)
    today = date.today()
    week = (
        week_summary(c, base.week_start_for(today))
        if race
        else {"workouts": [], "planned_km": 0, "actual_km": 0}
    )
    n = next(
        (
            w
            for w in week["workouts"]
            if w["status"] == "planned" and w["scheduled_date"] >= today.isoformat()
        ),
        None,
    )
    return {
        "today": today.isoformat(),
        "race": dict(race) if race else None,
        "assessment": base.goal_assessment(c, race) if race else None,
        "next_workout": n,
        "week": week,
        "profile": base.performance_profile(c, race),
        "pending_suggestions": c.execute(
            "SELECT COUNT(*) n FROM suggestions WHERE status='pending'"
        ).fetchone()["n"],
    }
