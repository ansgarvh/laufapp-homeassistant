from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from fastapi import HTTPException, Query
from pydantic import BaseModel, Field

import coach as coach_module
import db as db_module
import main as legacy
import training as legacy_training
import training_v020 as training
from db import db_conn, get_setting, set_setting

APP_VERSION = "0.2.0"

# db._defaults()/init_db resolve this module global at runtime. Keep the
# persistent app_version marker aligned with the Home Assistant release even
# though v0.2 deliberately reuses the unchanged schema-4 database module.
db_module.APP_VERSION = APP_VERSION

# Keep the mature v0.1.9 API surface and security middleware, but replace the
# planner globals used by its endpoint functions. Python resolves these globals
# when an endpoint is called, so the existing API remains backward compatible.
for _name in (
    "current_race",
    "generate_week",
    "week_summary",
    "dashboard",
    "automatic_max_weekly_km",
    "refresh_plan",
):
    setattr(legacy, _name, getattr(training, _name))

# Functions inside training.py / coach.py also resolve their module globals at
# runtime. Point their focus-race helpers at the multi-A-race implementation.
legacy_training.current_race = training.current_race
for _name in ("current_race", "generate_week", "week_summary"):
    if hasattr(coach_module, _name):
        setattr(coach_module, _name, getattr(training, _name))

legacy.APP_VERSION = APP_VERSION
legacy.app.version = APP_VERSION
app = legacy.app


class RaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    distance_km: float = Field(gt=1, le=100)
    race_date: date
    goal_seconds: int = Field(gt=300, le=24 * 3600)
    priority: Literal["A", "B"] = "A"


class RaceUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    distance_km: float = Field(gt=1, le=100)
    race_date: date
    goal_seconds: int = Field(gt=300, le=24 * 3600)
    priority: Literal["A", "B"]


class RunShoePayload(BaseModel):
    shoe_id: int | None = None


def _priority_map(c) -> dict[str, str]:
    raw = get_setting(c, "race_priorities", {}) or {}
    return {str(k): ("B" if str(v).upper() == "B" else "A") for k, v in dict(raw).items()}


def _set_priority(c, race_id: int, priority: str) -> None:
    mapping = _priority_map(c)
    mapping[str(int(race_id))] = priority
    set_setting(c, "race_priorities", mapping)


def _remove_priority(c, race_id: int) -> None:
    mapping = _priority_map(c)
    mapping.pop(str(int(race_id)), None)
    set_setting(c, "race_priorities", mapping)


def _race_week(d: date) -> tuple[date, date]:
    start = legacy.week_start_for(d)
    return start, start + timedelta(days=6)


def _validate_race_week(c, race_date: date, exclude_id: int | None = None) -> None:
    start, end = _race_week(race_date)
    args: list[object] = [start.isoformat(), end.isoformat()]
    sql = "SELECT id,name,race_date FROM races WHERE active=1 AND race_date BETWEEN ? AND ?"
    if exclude_id is not None:
        sql += " AND id!=?"
        args.append(int(exclude_id))
    other = c.execute(sql + " ORDER BY race_date,id", tuple(args)).fetchone()
    if other:
        raise HTTPException(
            409,
            f"In dieser Kalenderwoche ist bereits '{other['name']}' eingetragen. "
            "Bitte nur ein Rennen pro Trainingswoche planen.",
        )


def _race_dict(c, r) -> dict:
    d = dict(r)
    d["priority"] = training.race_priority(c, int(r["id"]))
    p = legacy.predict_distance(c, float(r["distance_km"]))
    d["recommendation"] = (
        {
            "predicted_seconds": p["predicted_seconds"],
            "predicted_time": p["predicted_time"],
            "range_text": p["range_text"],
            "confidence": p["confidence"],
        }
        if p
        else None
    )
    focus = training.current_race(c)
    d["is_focus"] = bool(focus and int(focus["id"]) == int(r["id"]))
    return d


@app.get("/api/v2/races")
def api_v2_races():
    with db_conn() as c:
        return [
            _race_dict(c, r)
            for r in c.execute(
                "SELECT * FROM races ORDER BY race_date,id"
            ).fetchall()
        ]


@app.get("/api/v2/races/recommendation")
def api_v2_race_recommendation(distance_km: float = Query(gt=1, le=100)):
    with db_conn() as c:
        p = legacy.predict_distance(c, distance_km)
        if not p:
            return {"available": False}
        return {
            "available": True,
            "predicted_seconds": p["predicted_seconds"],
            "predicted_time": p["predicted_time"],
            "range_text": p["range_text"],
            "confidence": p["confidence"],
        }


@app.post("/api/v2/races", status_code=201)
def api_v2_race_add(p: RaceCreate):
    if p.race_date <= date.today():
        raise HTTPException(400, "Das Wettkampfdatum muss in der Zukunft liegen.")
    with db_conn() as c:
        _validate_race_week(c, p.race_date)
        cur = c.execute(
            "INSERT INTO races(name,distance_km,race_date,goal_seconds,target_source,active) "
            "VALUES(?,?,?,?, 'user',1)",
            (p.name, p.distance_km, p.race_date.isoformat(), p.goal_seconds),
        )
        rid = int(cur.lastrowid)
        _set_priority(c, rid, p.priority)
        legacy.mark_plan_stale(c, "Wettkampfplanung geändert")
        return _race_dict(c, c.execute("SELECT * FROM races WHERE id=?", (rid,)).fetchone())


@app.put("/api/v2/races/{rid}")
def api_v2_race_update(rid: int, p: RaceUpdate):
    if p.race_date <= date.today():
        raise HTTPException(400, "Das Wettkampfdatum muss in der Zukunft liegen.")
    with db_conn() as c:
        if not c.execute("SELECT id FROM races WHERE id=?", (rid,)).fetchone():
            raise HTTPException(404, "Wettkampf nicht gefunden.")
        _validate_race_week(c, p.race_date, rid)
        c.execute(
            "UPDATE races SET name=?,distance_km=?,race_date=?,goal_seconds=?,target_source='user',active=1 "
            "WHERE id=?",
            (p.name, p.distance_km, p.race_date.isoformat(), p.goal_seconds, rid),
        )
        _set_priority(c, rid, p.priority)
        legacy.mark_plan_stale(c, "Wettkampfplanung geändert")
        return _race_dict(c, c.execute("SELECT * FROM races WHERE id=?", (rid,)).fetchone())


@app.delete("/api/v2/races/{rid}")
def api_v2_race_delete(rid: int):
    with db_conn() as c:
        r = c.execute("SELECT * FROM races WHERE id=?", (rid,)).fetchone()
        if not r:
            raise HTTPException(404, "Wettkampf nicht gefunden.")
        c.execute("DELETE FROM races WHERE id=?", (rid,))
        _remove_priority(c, rid)
        legacy.mark_plan_stale(c, "Wettkampfplanung geändert")
        return {"ok": True}


def _run_with_shoe(c, rid: int):
    return c.execute(
        "SELECT r.*,s.brand shoe_brand,s.model shoe_model,s.nickname shoe_nickname "
        "FROM runs r LEFT JOIN shoes s ON s.id=r.shoe_id WHERE r.id=?",
        (rid,),
    ).fetchone()


def _same_day_runs(c, scheduled_date: str):
    return c.execute(
        "SELECT * FROM runs WHERE substr(started_at,1,10)=? ORDER BY started_at,id",
        (scheduled_date,),
    ).fetchall()


@app.get("/api/v2/workouts/{wid}/run-info")
def api_v2_workout_run_info(wid: int):
    with db_conn() as c:
        w = c.execute("SELECT * FROM workouts WHERE id=?", (wid,)).fetchone()
        if not w:
            raise HTTPException(404, "Training nicht gefunden.")
        run = _run_with_shoe(c, int(w["linked_run_id"])) if w["linked_run_id"] else None
        candidates = [] if run else _same_day_runs(c, w["scheduled_date"])
        return {
            "workout": dict(w),
            "run": dict(run) if run else None,
            "single_same_day_candidate": dict(candidates[0]) if len(candidates) == 1 else None,
            "same_day_candidates": len(candidates),
        }


@app.patch("/api/v2/workouts/{wid}/shoe")
def api_v2_workout_shoe(wid: int, p: RunShoePayload):
    with db_conn() as c:
        w = c.execute("SELECT * FROM workouts WHERE id=?", (wid,)).fetchone()
        if not w:
            raise HTTPException(404, "Training nicht gefunden.")
        if w["status"] != "completed":
            raise HTTPException(400, "Ein Schuh kann hier erst nach Abschluss der Einheit zugeordnet werden.")

        run_id = int(w["linked_run_id"]) if w["linked_run_id"] else None
        if run_id is None:
            candidates = _same_day_runs(c, w["scheduled_date"])
            if len(candidates) == 1:
                run_id = int(candidates[0]["id"])
                c.execute("UPDATE workouts SET linked_run_id=? WHERE id=?", (run_id, wid))
            elif not candidates:
                raise HTTPException(
                    400,
                    "Für diese absolvierte Einheit ist noch kein Laufdatensatz vorhanden. "
                    "Bitte den Lauf zuerst importieren oder manuell eintragen.",
                )
            else:
                raise HTTPException(
                    409,
                    "An diesem Tag wurden mehrere Läufe gefunden. Bitte den Schuh im Fortschritt-Tab beim konkreten Lauf zuordnen.",
                )

        if p.shoe_id is not None:
            shoe = c.execute(
                "SELECT id FROM shoes WHERE id=? AND archived=0", (p.shoe_id,)
            ).fetchone()
            if not shoe:
                raise HTTPException(400, "Schuh nicht gefunden oder archiviert.")

        c.execute("UPDATE runs SET shoe_id=? WHERE id=?", (p.shoe_id, run_id))
        run = _run_with_shoe(c, run_id)
        return {"ok": True, "run": dict(run) if run else None}
