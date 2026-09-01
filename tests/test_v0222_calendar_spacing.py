import json
from datetime import date

from db import db_conn


def _workouts(client):
    response = client.get("/api/week")
    assert response.status_code == 200, response.text
    return response.json()


def _swap_engine_dates(first: dict, second: dict) -> None:
    with db_conn() as c:
        c.execute(
            "UPDATE workouts SET scheduled_date=CASE id WHEN ? THEN ? WHEN ? THEN ? ELSE scheduled_date END "
            "WHERE id IN (?,?)",
            (
                int(first["id"]), second["scheduled_date"],
                int(second["id"]), first["scheduled_date"],
                int(first["id"]), int(second["id"]),
            ),
        )


def _make_longrun_key(longrun: dict) -> None:
    with db_conn() as c:
        row = c.execute("SELECT details_json FROM workouts WHERE id=?", (int(longrun["id"]),)).fetchone()
        details = json.loads(row["details_json"] or "{}")
        details.setdefault("load", {})["long_run_duration_min"] = 180
        c.execute(
            "UPDATE workouts SET distance_km=30,details_json=? WHERE id=?",
            (json.dumps(details, ensure_ascii=False), int(longrun["id"])),
        )


def test_legacy_engine_week_is_healed_to_quality_then_easy(setup_client):
    initial = _workouts(setup_client)
    workouts = initial["workouts"]
    completed = min(
        (w for w in workouts if w["workout_type"] == "easy"),
        key=lambda w: w["scheduled_date"],
    )
    marked = setup_client.post(
        f"/api/workouts/{completed['id']}/status",
        json={"status": "completed"},
    )
    assert marked.status_code == 200, marked.text
    quality = next(w for w in workouts if w["workout_type"] == "quality")
    following_easy = next(
        w for w in workouts
        if w["workout_type"] == "easy" and w["scheduled_date"] > quality["scheduled_date"]
    )
    assert (date.fromisoformat(following_easy["scheduled_date"]) - date.fromisoformat(quality["scheduled_date"])).days == 1

    _swap_engine_dates(quality, following_easy)
    healed = _workouts(setup_client)
    quality_after = next(w for w in healed["workouts"] if w["id"] == quality["id"])
    easy_after = next(w for w in healed["workouts"] if w["id"] == following_easy["id"])
    completed_after = next(w for w in healed["workouts"] if w["id"] == completed["id"])
    assert quality_after["scheduled_date"] == quality["scheduled_date"]
    assert easy_after["scheduled_date"] == following_easy["scheduled_date"]
    assert completed_after["scheduled_date"] == completed["scheduled_date"]
    assert completed_after["status"] == "completed"
    assert completed_after["manual_override"] == 1
    assert healed["guardrails"]["calendar_spacing"]["quality_before_easy_ok"] is True


def test_very_long_run_gets_at_least_two_calendar_days_from_quality(setup_client):
    assert setup_client.patch("/api/settings", json={"training_days": [1, 3, 5, 6]}).status_code == 200
    assert setup_client.post("/api/plan/refresh?weeks=1").status_code == 200
    initial = _workouts(setup_client)
    quality = next(w for w in initial["workouts"] if w["workout_type"] == "quality")
    later_easy = next(
        w for w in initial["workouts"]
        if w["workout_type"] == "easy" and w["scheduled_date"] > quality["scheduled_date"]
    )
    longrun = next(w for w in initial["workouts"] if w["workout_type"] == "long")
    _make_longrun_key(longrun)
    _swap_engine_dates(quality, later_easy)

    healed = _workouts(setup_client)
    quality_after = next(w for w in healed["workouts"] if w["id"] == quality["id"])
    long_after = next(w for w in healed["workouts"] if w["id"] == longrun["id"])
    gap = (
        date.fromisoformat(long_after["scheduled_date"])
        - date.fromisoformat(quality_after["scheduled_date"])
    ).days
    assert gap >= 2
    spacing = healed["guardrails"]["calendar_spacing"]
    assert spacing["minimum_key_session_gap_hours"] == 48
    assert spacing["key_session_spacing_ok"] is True


def test_manual_quality_easy_swap_is_preserved_and_reported(setup_client):
    initial = _workouts(setup_client)
    quality = next(w for w in initial["workouts"] if w["workout_type"] == "quality")
    following_easy = next(
        w for w in initial["workouts"]
        if w["workout_type"] == "easy" and w["scheduled_date"] > quality["scheduled_date"]
    )
    moved = setup_client.post(
        f"/api/workouts/{quality['id']}/move",
        json={"scheduled_date": following_easy["scheduled_date"]},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["operation"] == "swap"

    preserved = _workouts(setup_client)
    quality_after = next(w for w in preserved["workouts"] if w["id"] == quality["id"])
    easy_after = next(w for w in preserved["workouts"] if w["id"] == following_easy["id"])
    assert quality_after["scheduled_date"] == following_easy["scheduled_date"]
    assert easy_after["scheduled_date"] == quality["scheduled_date"]
    spacing = preserved["guardrails"]["calendar_spacing"]
    assert spacing["quality_before_easy_ok"] is False
    assert preserved["guardrails"]["needs_review"] is True
    assert any("Qualität → Easy" in alert["text"] for alert in preserved["guardrails"]["alerts"])


def test_manual_key_session_conflict_is_not_silently_undone(setup_client):
    assert setup_client.patch("/api/settings", json={"training_days": [1, 3, 5, 6]}).status_code == 200
    assert setup_client.post("/api/plan/refresh?weeks=1").status_code == 200
    initial = _workouts(setup_client)
    quality = next(w for w in initial["workouts"] if w["workout_type"] == "quality")
    later_easy = next(
        w for w in initial["workouts"]
        if w["workout_type"] == "easy" and w["scheduled_date"] > quality["scheduled_date"]
    )
    longrun = next(w for w in initial["workouts"] if w["workout_type"] == "long")
    _make_longrun_key(longrun)
    moved = setup_client.post(
        f"/api/workouts/{quality['id']}/move",
        json={"scheduled_date": later_easy["scheduled_date"]},
    )
    assert moved.status_code == 200, moved.text

    preserved = _workouts(setup_client)
    quality_after = next(w for w in preserved["workouts"] if w["id"] == quality["id"])
    long_after = next(w for w in preserved["workouts"] if w["id"] == longrun["id"])
    assert quality_after["scheduled_date"] == later_easy["scheduled_date"]
    assert (
        date.fromisoformat(long_after["scheduled_date"])
        - date.fromisoformat(quality_after["scheduled_date"])
    ).days == 1
    spacing = preserved["guardrails"]["calendar_spacing"]
    assert spacing["key_session_spacing_ok"] is False
    assert preserved["guardrails"]["needs_review"] is True
    assert any("Mindestens 48 h" in alert["text"] for alert in preserved["guardrails"]["alerts"])
