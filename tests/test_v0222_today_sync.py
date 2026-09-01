import json
from pathlib import Path

from db import db_conn


ROOT = Path(__file__).resolve().parents[1]
STRONG_TOKEN = "9f4a6c2d8e1b7a305c9d4e6f1a2b8c70d5e3f9a1c6b4d8e2f7a0c3b5d9e1f6a4"


def _insert_import_job(c, *, job_uuid: str, status: str, finished_at: str | None) -> None:
    c.execute(
        "INSERT INTO import_jobs(job_uuid,import_type,original_name,status,phase,progress,finished_at) "
        "VALUES(?, 'apple_health', 'export.zip', ?, ?, ?, ?)",
        (
            job_uuid,
            status,
            "Fertig" if status == "completed" else "Fehler",
            1 if status == "completed" else 0,
            finished_at,
        ),
    )


def test_dashboard_uses_newest_successful_sync_and_ignores_failures(setup_client):
    assert setup_client.get("/api/dashboard").json()["data_sync"] is None
    with db_conn() as c:
        c.execute(
            "INSERT INTO settings(key,value) VALUES('health_auto_export_last_sync',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (json.dumps("2026-09-01T08:15:00+00:00"),),
        )
        _insert_import_job(
            c,
            job_uuid="completed-older",
            status="completed",
            finished_at="2026-09-01 07:45:00",
        )
        _insert_import_job(
            c,
            job_uuid="failed-newer",
            status="failed",
            finished_at="2026-09-01 10:00:00",
        )

    sync = setup_client.get("/api/dashboard").json()["data_sync"]
    assert sync == {
        "at": "2026-09-01T08:15:00Z",
        "source": "health_auto_export",
    }

    with db_conn() as c:
        _insert_import_job(
            c,
            job_uuid="completed-newer",
            status="completed",
            finished_at="2026-09-01 09:30:00",
        )
    sync = setup_client.get("/api/dashboard").json()["data_sync"]
    assert sync == {
        "at": "2026-09-01T09:30:00Z",
        "source": "apple_health_import",
    }


def test_malformed_hae_timestamp_does_not_break_completed_import_fallback(setup_client):
    with db_conn() as c:
        c.execute(
            "INSERT INTO settings(key,value) VALUES('health_auto_export_last_sync',?)",
            ("not-a-timestamp",),
        )
        _insert_import_job(
            c,
            job_uuid="valid-completed",
            status="completed",
            finished_at="2026-08-31 22:10:00",
        )
    response = setup_client.get("/api/dashboard")
    assert response.status_code == 200, response.text
    assert response.json()["data_sync"] == {
        "at": "2026-08-31T22:10:00Z",
        "source": "apple_health_import",
    }


def test_successful_hae_api_sync_is_immediately_visible_on_dashboard(setup_client, monkeypatch):
    monkeypatch.setenv("LAUFAPP_HEALTH_AUTO_EXPORT_TOKEN", STRONG_TOKEN)
    response = setup_client.post(
        "/api/v2/health-auto-export",
        headers={"Authorization": f"Bearer {STRONG_TOKEN}"},
        json={"data": {"workouts": [], "metrics": []}},
    )
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
    sync = setup_client.get("/api/dashboard").json()["data_sync"]
    assert sync["source"] == "health_auto_export"
    assert sync["at"].endswith("Z")


def test_today_sync_indicator_is_above_next_workout_and_has_empty_state():
    js = (ROOT / "laufapp/app/static/app.js").read_text(encoding="utf-8")
    css = (ROOT / "laufapp/app/static/assets/v0222.css").read_text(encoding="utf-8")
    index = (ROOT / "laufapp/app/static/index.html").read_text(encoding="utf-8")
    start = js.index("async function renderToday")
    end = js.index("function metric", start)
    today = js[start:end]
    assert today.index("dataSyncStatus(d.data_sync)") < today.index("<h2>Nächste Einheit</h2>")
    assert "Daten zuletzt synchronisiert" in js
    assert "Noch keine erfolgreiche Synchronisierung" in js
    assert "Health Auto Export" in js and "Apple-Health-Import" in js
    assert ".today-data-sync" in css
    assert "assets/v0222.css?v=0.2.22" in index
