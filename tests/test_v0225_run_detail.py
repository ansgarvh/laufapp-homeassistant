from datetime import datetime, timedelta
import math


def _insert_sample(c, run_id, external_id, metric, at, value, unit):
    c.execute(
        "INSERT INTO run_samples(external_id,run_id,metric_type,sampled_at,value,unit,source) VALUES(?,?,?,?,?,?,?)",
        (external_id, run_id, metric, at, value, unit, "test"),
    )


def test_detailed_completed_run_endpoint_and_runtime_assets(setup_client):
    client = setup_client
    start = datetime.fromisoformat("2026-09-01T05:58:00+02:00")
    created = client.post(
        "/api/runs",
        json={
            "started_at": start.isoformat(),
            "distance_km": 14.04,
            "duration_s": 4593,
            "avg_hr": 127,
            "elevation_m": 148,
            "calories": 1142,
            "rpe": 5,
            "notes": "Ruhiger Dauerlauf",
            "source": "apple_health_hae",
        },
    )
    assert created.status_code == 200, created.text
    run_id = int(created.json()["id"])

    from db import db_conn

    with db_conn() as c:
        c.execute(
            "UPDATE runs SET ended_at=? WHERE id=?",
            ((start + timedelta(seconds=4604)).isoformat(), run_id),
        )
        for i, value in enumerate((120, 127, 134)):
            _insert_sample(c, run_id, f"hr-{i}", "heart_rate", (start + timedelta(minutes=10 * i)).isoformat(), value, "bpm")
        for i, value in enumerate((270, 280, 290)):
            _insert_sample(c, run_id, f"power-{i}", "running_power", (start + timedelta(minutes=10 * i)).isoformat(), value, "W")
        for i, value in enumerate((157, 158, 159)):
            _insert_sample(c, run_id, f"cad-{i}", "cadence", (start + timedelta(minutes=10 * i)).isoformat(), value, "spm")
        for i, value in enumerate((108, 110, 112)):
            _insert_sample(c, run_id, f"stride-{i}", "stride_length", (start + timedelta(minutes=10 * i)).isoformat(), value, "cm")
        for i, value in enumerate((0.100, 0.105, 0.110)):
            _insert_sample(c, run_id, f"vo-{i}", "vertical_oscillation", (start + timedelta(minutes=10 * i)).isoformat(), value, "m")
        for i, value in enumerate((0.250, 0.259, 0.268)):
            _insert_sample(c, run_id, f"gct-{i}", "ground_contact_time", (start + timedelta(minutes=10 * i)).isoformat(), value, "s")
        for i in range(300):
            speed_kmh = (10.8, 11.0, 11.2)[i % 3]
            _insert_sample(c, run_id, f"speed-{i}", "running_speed", (start + timedelta(seconds=i * 12)).isoformat(), speed_kmh, "km/h")
        for i in range(750):
            c.execute(
                "INSERT INTO gps_points(run_id,sampled_at,latitude,longitude,elevation_m,sequence,source) VALUES(?,?,?,?,?,?,?)",
                (
                    run_id,
                    (start + timedelta(seconds=i * 6)).isoformat(),
                    50.7750 + i * 0.00001,
                    6.0830 + math.sin(i / 45) * 0.003 + i * 0.000004,
                    165 + math.sin(i / 80) * 18,
                    i,
                    "test",
                ),
            )

    response = client.get(f"/api/v2/runs/{run_id}/detail-view")
    assert response.status_code == 200, response.text
    data = response.json()
    summary = data["summary"]
    assert data["schema"] == 1
    assert summary["distance_km"] == 14.04
    assert summary["training_time_s"] == 4593
    assert summary["elapsed_time_s"] == 4604
    assert abs(summary["pace_s_per_km"] - (4593 / 14.04)) < 0.02
    assert summary["elevation_gain_m"] == 148
    assert summary["average_heart_rate_bpm"] == 127
    assert summary["average_power_w"] == 280
    assert summary["average_cadence_spm"] == 158
    assert summary["active_calories_kcal"] == 1142
    assert summary["total_calories_kcal"] is None
    assert summary["effort_rpe"] == 5 and summary["effort_label"] == "Mäßig"
    assert summary["stride_length_m"] == 1.1
    assert summary["vertical_oscillation_cm"] == 10.5
    assert summary["ground_contact_time_ms"] == 259

    series = data["series"]
    assert set(("heart_rate", "running_speed", "pace", "running_power", "cadence", "stride_length", "vertical_oscillation", "ground_contact_time", "elevation")).issubset(series)
    assert series["running_speed"]["samples"] == 300
    assert len(series["running_speed"]["points"]) <= 240
    assert len(series["pace"]["points"]) <= 240
    assert series["stride_length"]["unit"] == "m"
    assert series["vertical_oscillation"]["unit"] == "cm"
    assert series["ground_contact_time"]["unit"] == "ms"

    route = data["route"]
    assert route["available"] is True
    assert route["original_points"] == 750
    assert len(route["points"]) <= 700
    assert route["points"][0]["lat"] == 50.775
    assert "lokal" in route["privacy_note"].casefold()
    assert "nicht" in data["notes"]["total_calories"].casefold()

    root = client.get("/")
    assert root.status_code == 200
    assert 'assets/v0225.css?v=0.2.25' in root.text
    assert 'assets/v0225.js?v=0.2.25' in root.text


def test_separate_total_calories_are_exposed_without_overwriting_active(client):
    start = datetime.fromisoformat("2026-09-01T06:00:00+02:00")
    created = client.post(
        "/api/runs",
        json={
            "started_at": start.isoformat(),
            "distance_km": 10.0,
            "duration_s": 3300,
            "calories": 700,
            "source": "apple_health_hae",
        },
    )
    assert created.status_code == 200, created.text
    run_id = int(created.json()["id"])

    from db import db_conn
    with db_conn() as c:
        _insert_sample(c, run_id, "total-energy-test", "total_calories", start.isoformat(), 805.5, "kcal")

    response = client.get(f"/api/v2/runs/{run_id}/detail-view")
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["active_calories_kcal"] == 700
    assert summary["total_calories_kcal"] == 805.5
    assert "separat" in response.json()["notes"]["total_calories"].casefold()


def test_run_detail_missing_run_is_404(client):
    response = client.get("/api/v2/runs/999999/detail-view")
    assert response.status_code == 404
    assert "Lauf nicht gefunden" in response.text
