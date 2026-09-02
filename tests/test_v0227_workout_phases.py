import json

import pytest

from db import CURRENT_SCHEMA_VERSION, db_conn
from workout_phases_v0227 import PHASE_SCHEMA_VERSION, _VARIANT_SPECS, enrich_workout


def _workout(**changes):
    base = {
        "id": 1,
        "workout_type": "quality",
        "title": "MARATHONPACE · kontrollierter Dauerblock",
        "distance_km": 11.4,
        "pace_low_s_per_km": 279,
        "pace_high_s_per_km": 289,
        "details": {
            "variant_key": "mp_continuous",
            "physiological_target": "marathon_specific",
            "rpe_target": "6–7/10",
            "load": {"distance_km": 11.4, "moderate_min": 35},
            "plan_basis": {
                "training_paces": {
                    "training_marathon_pace_s_per_km": 284,
                }
            },
        },
    }
    base.update(changes)
    return base


def test_continuous_quality_has_exact_warmup_work_and_cooldown_distance():
    workout = enrich_workout(_workout())
    details = workout["details"]
    phases = details["phases"]
    assert details["phase_schema_version"] == PHASE_SCHEMA_VERSION
    assert [phase["kind"] for phase in phases] == ["warmup", "work", "cooldown"]
    assert [phase["label"] for phase in phases] == ["Einlaufen", "Hauptteil", "Auslaufen"]
    assert sum(float(phase.get("distance_km") or 0) for phase in phases) == 11.4
    assert phases[0]["distance_km"] == 2.0
    assert phases[1]["distance_km"] == 7.4
    assert phases[2]["distance_km"] == 2.0
    assert phases[0]["pace_text"] == "5:39–6:19/km"
    assert phases[1]["pace_text"] == "4:39–4:49/km"
    assert details["primary_pace_text"] == "4:39–4:49/km"


def test_distance_intervals_include_repetitions_and_time_recovery():
    raw = _workout(
        title="SCHWELLE · 4 × 2 km",
        distance_km=12.0,
        pace_low_s_per_km=255,
        pace_high_s_per_km=265,
    )
    raw["details"].update(
        variant_key="thr_4x2k",
        physiological_target="threshold",
        load={"distance_km": 12, "moderate_min": 34},
    )
    phases = enrich_workout(raw)["details"]["phases"]
    assert [phase["kind"] for phase in phases] == ["warmup", "work", "recovery", "cooldown"]
    work = phases[1]
    recovery = phases[2]
    assert work["target_text"] == "4 × 2 km"
    assert work["repetitions"] == 4
    assert work["repeat_distance_km"] == 2.0
    assert recovery["target_text"] == "3 × 2 min"
    assert recovery["duration_s"] == 120
    assert recovery["counted_in_distance"] is False
    assert "tatsächlich aufgezeichnete Distanz" in enrich_workout(raw)["details"]["distance_note"]


@pytest.mark.parametrize("variant_key", sorted(_VARIANT_SPECS))
def test_every_quality_variant_has_a_complete_explicit_phase_contract(variant_key):
    raw = _workout(distance_km=14.0)
    raw["details"].update(
        variant_key=variant_key,
        load={"distance_km": 14.0, "moderate_min": 28.0, "high_min": 8.0},
    )
    details = enrich_workout(raw)["details"]
    phases = details["phases"]
    assert phases[0]["kind"] == "warmup"
    assert phases[-1]["kind"] == "cooldown"
    assert any(phase["kind"] == "work" for phase in phases)
    assert [phase["order"] for phase in phases] == list(range(1, len(phases) + 1))
    assert all(phase["target_text"] and phase["instruction"] for phase in phases)
    assert details["primary_pace_text"] == "4:39–4:49/km"


def test_generic_marathon_pace_blocks_include_between_block_recovery():
    raw = _workout(distance_km=11.4)
    raw["details"].update(variant_key="mp_blocks")
    phases = enrich_workout(raw)["details"]["phases"]
    recovery = next(phase for phase in phases if phase["kind"] == "recovery")
    assert recovery["label"] == "Erholung zwischen Wiederholungen"
    assert recovery["target_text"] == "1 × lockerer Zwischenabschnitt"


def test_marathon_specific_long_run_separates_blocks_and_easy_sections():
    raw = _workout(
        workout_type="long",
        title="MARATHON-SPECIFIC · 30 km inkl. 10 km MP",
        distance_km=30,
        pace_low_s_per_km=279,
        pace_high_s_per_km=289,
    )
    raw["details"].update(variant_key="long_mp_blocks", mp_km=10)
    phases = enrich_workout(raw)["details"]["phases"]
    assert [phase["kind"] for phase in phases] == ["warmup", "work", "recovery", "cooldown"]
    assert phases[1]["distance_km"] == 10
    assert phases[1]["repetitions"] == 3
    assert phases[2]["counted_in_distance"] is True
    assert sum(float(phase.get("distance_km") or 0) for phase in phases) == 30


def test_legacy_easy_workout_without_science_metadata_remains_readable():
    workout = enrich_workout(
        {
            "workout_type": "easy",
            "title": "Easy Run",
            "distance_km": 8,
            "pace_low_s_per_km": 335,
            "pace_high_s_per_km": 375,
            "details": {},
        }
    )
    phases = workout["details"]["phases"]
    assert len(phases) == 1
    assert phases[0]["label"] == "Lockerer Lauf"
    assert phases[0]["distance_km"] == 8


def test_week_and_dashboard_expose_phases_without_schema_migration(setup_client):
    week_response = setup_client.get("/api/week")
    assert week_response.status_code == 200, week_response.text
    week = week_response.json()
    assert week["workouts"]
    for workout in week["workouts"]:
        details = workout["details"]
        assert details["phase_schema_version"] == PHASE_SCHEMA_VERSION
        assert details["phases"]
        assert [phase["order"] for phase in details["phases"]] == list(
            range(1, len(details["phases"]) + 1)
        )

    quality = next(workout for workout in week["workouts"] if workout["workout_type"] == "quality")
    kinds = [phase["kind"] for phase in quality["details"]["phases"]]
    assert kinds[0] == "warmup"
    assert "work" in kinds
    assert kinds[-1] == "cooldown"

    dashboard = setup_client.get("/api/dashboard")
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["next_workout"]["details"]["phases"]

    with db_conn() as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == CURRENT_SCHEMA_VERSION
        stored = c.execute(
            "SELECT details_json FROM workouts WHERE id=?", (int(quality["id"]),)
        ).fetchone()
        # Phases are a compatible API projection. Existing rows are deliberately
        # not rewritten merely because the user opened the week.
        assert "phases" not in json.loads(stored["details_json"] or "{}")


def test_phase_ui_assets_and_labels_are_served(client):
    root = client.get("/")
    assert root.status_code == 200
    assert 'assets/v0227.css?v=0.2.27' in root.text

    app_js = client.get("/app.js?v=0.2.27")
    assert app_js.status_code == 200
    assert "function workoutPhasesHtml" in app_js.text
    assert all(label in app_js.text for label in ["Ablauf", "Gesamtdistanz", "Hauptteil"])
