import json
from pathlib import Path
from types import SimpleNamespace

from db import db_conn


ROOT = Path(__file__).resolve().parents[1]


def _response(payload, *, with_source=True):
    annotation = SimpleNamespace(
        url="https://pubmed.ncbi.nlm.nih.gov/example", title="Sportwissenschaftliche Quelle"
    )
    content = SimpleNamespace(annotations=[annotation] if with_source else [])
    output = [
        SimpleNamespace(type="web_search_call", content=[]),
        SimpleNamespace(type="message", content=[content]),
    ]
    return SimpleNamespace(
        output_text=json.dumps(payload),
        usage=SimpleNamespace(input_tokens=1200, output_tokens=450),
        output=output,
    )


def _analysis_payload(suggestion=None):
    return {
        "summary": "Die Einheit wurde insgesamt kontrolliert absolviert.",
        "sections": {
            "plan_comparison": "Distanz und Belastung passen zur verknüpften Einheit.",
            "pacing": "Die Pace blieb im verfügbaren Verlauf stabil.",
            "cardiovascular": "Die Herzfrequenzdrift ist gering und nur als Schätzung zu lesen.",
            "running_dynamics": "Kadenz und Power werden gegen die persönliche Basis eingeordnet.",
            "recovery": "Die vorhandenen Recovery-Signale ergeben keinen klaren Warnhinweis.",
        },
        "next_step": "Den nächsten Easy Run bewusst locker halten.",
        "data_quality": "Herzfrequenz und Laufdynamik vorhanden; GPS-Splits nur näherungsweise.",
        "suggestion": suggestion,
    }


def _add_detailed_run(client):
    workout = client.get("/api/week").json()["workouts"][0]
    response = client.post(
        "/api/runs",
        json={
            "started_at": workout["scheduled_date"] + "T08:00:00+02:00",
            "distance_km": workout["distance_km"],
            "duration_s": max(1800, workout["distance_km"] * 330),
            "avg_hr": 146,
            "elevation_m": 85,
            "rpe": 4,
            "notes": "Kontrolliert, keine Beschwerden.",
            "source": "manual",
        },
    )
    assert response.status_code == 200, response.text
    run_id = response.json()["id"]
    with db_conn() as c:
        for index in range(10):
            stamp = f"{workout['scheduled_date']}T08:{index:02d}:00+02:00"
            c.execute(
                "INSERT INTO run_samples(external_id,run_id,metric_type,sampled_at,value,unit) "
                "VALUES(?,?,?,?,?,?)",
                (f"hr-{run_id}-{index}", run_id, "heart_rate", stamp, 140 + index, "bpm"),
            )
            c.execute(
                "INSERT INTO run_samples(external_id,run_id,metric_type,sampled_at,value,unit) "
                "VALUES(?,?,?,?,?,?)",
                (f"power-{run_id}-{index}", run_id, "running_power", stamp, 295 + index, "W"),
            )
            c.execute(
                "INSERT INTO run_samples(external_id,run_id,metric_type,sampled_at,value,unit) "
                "VALUES(?,?,?,?,?,?)",
                (f"cad-{run_id}-{index}", run_id, "cadence", stamp, 168 + index / 10, "spm"),
            )
        c.execute(
            "INSERT INTO gps_points(run_id,sampled_at,latitude,longitude,elevation_m,sequence,source) "
            "VALUES(?,?,?,?,?,0,'test')",
            (run_id, workout["scheduled_date"] + "T08:00:00+02:00", 50.775, 6.083, 180),
        )
        c.execute(
            "INSERT INTO gps_points(run_id,sampled_at,latitude,longitude,elevation_m,sequence,source) "
            "VALUES(?,?,?,?,?,1,'test')",
            (run_id, workout["scheduled_date"] + "T08:10:00+02:00", 50.784, 6.083, 184),
        )
    return run_id, workout


def test_openai_requests_are_stateless_and_schema_constrained(monkeypatch):
    import coach
    import openai

    captured = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _response({"reply": "ok", "suggestion": None}, with_source=False)

    class FakeClient:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    schema = {
        "name": "test_schema",
        "description": "test",
        "schema": {
            "type": "object",
            "properties": {"reply": {"type": "string"}},
            "required": ["reply"],
            "additionalProperties": False,
        },
    }
    coach.request("gpt-5.6-luna", "test", structured_output=schema, max_output_tokens=321)
    assert captured["store"] is False
    assert captured["text"]["format"]["type"] == "json_schema"
    assert captured["text"]["format"]["strict"] is True
    assert captured["text"]["format"]["name"] == "test_schema"
    assert captured["max_output_tokens"] == 321
    assert captured["api_key"] == "test-key"


def test_single_run_analysis_is_minimised_cached_and_explicitly_refreshed(
    setup_client, monkeypatch
):
    import coach

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    run_id, _ = _add_detailed_run(setup_client)
    absent = setup_client.get(f"/api/coach/runs/{run_id}/analysis")
    assert absent.status_code == 200
    assert absent.json() == {"available": False, "analysis": None, "stale": False}

    calls = []

    def fake_request(model, input_data, tools=None, **kwargs):
        calls.append(
            {"model": model, "input": input_data, "tools": tools, "kwargs": kwargs}
        )
        return _response(_analysis_payload())

    monkeypatch.setattr(coach, "request", fake_request)
    first = setup_client.post(f"/api/coach/runs/{run_id}/analysis")
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["cached"] is False
    assert body["analysis"]["run_id"] == run_id
    assert body["analysis"]["privacy"]["gps_coordinates_included"] is False
    assert len(calls) == 1
    transmitted = json.dumps(calls[0]["input"], ensure_ascii=False)
    assert "latitude" not in transmitted and "longitude" not in transmitted
    assert "50.775" not in transmitted and "6.083" not in transmitted
    assert calls[0]["kwargs"]["structured_output"]["name"] == "laufapp_run_analysis"

    cached = setup_client.post(f"/api/coach/runs/{run_id}/analysis")
    assert cached.status_code == 200 and cached.json()["cached"] is True
    assert len(calls) == 1
    stored = setup_client.get(f"/api/coach/runs/{run_id}/analysis").json()
    assert stored["available"] is True and stored["analysis"]["summary"] == body["analysis"]["summary"]

    refreshed = setup_client.post(f"/api/coach/runs/{run_id}/analysis?force=true")
    assert refreshed.status_code == 200 and refreshed.json()["cached"] is False
    assert len(calls) == 2


def test_changed_run_is_marked_stale_until_user_reanalyses(setup_client, monkeypatch):
    import coach

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    run_id, _ = _add_detailed_run(setup_client)
    monkeypatch.setattr(coach, "request", lambda *args, **kwargs: _response(_analysis_payload()))
    assert setup_client.post(f"/api/coach/runs/{run_id}/analysis").status_code == 200
    changed = setup_client.patch(f"/api/runs/{run_id}", json={"rpe": 7})
    assert changed.status_code == 200
    saved = setup_client.get(f"/api/coach/runs/{run_id}/analysis").json()
    assert saved["available"] is True
    assert saved["stale"] is True and saved["analysis"]["stale"] is True


def test_run_analysis_plan_change_remains_confirmation_gated(setup_client, monkeypatch):
    import coach

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    run_id, completed = _add_detailed_run(setup_client)
    open_workout = next(
        workout
        for workout in setup_client.get("/api/week").json()["workouts"]
        if workout["id"] != completed["id"] and workout["status"] == "planned"
    )
    proposed = max(3, float(open_workout["distance_km"]) - 1)
    suggestion = {
        "title": "Recovery-Anpassung",
        "rationale": "Den nächsten Reiz konservativ reduzieren.",
        "workout_id": open_workout["id"],
        "changes": {"distance_km": proposed, "scheduled_date": None},
    }
    monkeypatch.setattr(
        coach, "request", lambda *args, **kwargs: _response(_analysis_payload(suggestion))
    )
    result = setup_client.post(f"/api/coach/runs/{run_id}/analysis")
    assert result.status_code == 200, result.text
    suggestion_id = result.json()["suggestion_id"]
    before = next(
        row
        for row in setup_client.get("/api/week").json()["workouts"]
        if row["id"] == open_workout["id"]
    )["distance_km"]
    assert before == open_workout["distance_km"]
    accepted = setup_client.post(f"/api/suggestions/{suggestion_id}/accept")
    assert accepted.status_code == 200, accepted.text
    after = next(
        row
        for row in setup_client.get("/api/week").json()["workouts"]
        if row["id"] == open_workout["id"]
    )["distance_km"]
    assert after == proposed and after < before


def test_chat_uses_structured_output_and_local_history(setup_client, monkeypatch):
    import coach

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with db_conn() as c:
        c.execute("INSERT INTO chat_messages(role,text) VALUES('user','Vorherige Frage')")
        c.execute("INSERT INTO chat_messages(role,text) VALUES('assistant','Vorherige Antwort')")
    calls = []

    def fake_request(model, input_data, tools=None, **kwargs):
        calls.append((input_data, kwargs))
        return _response({"reply": "Konkrete neue Antwort", "suggestion": None})

    monkeypatch.setattr(coach, "request", fake_request)
    response = setup_client.post("/api/coach/chat", json={"message": "Und was folgt daraus?"})
    assert response.status_code == 200, response.text
    assert response.json()["reply"] == "Konkrete neue Antwort"
    assert calls[0][1]["structured_output"]["name"] == "laufapp_coach_reply"
    sent = json.dumps(calls[0][0], ensure_ascii=False)
    assert "Vorherige Frage" in sent and "Vorherige Antwort" in sent


def test_v023_ui_exposes_per_run_feedback_without_raw_gps_disclosure():
    js = (ROOT / "laufapp/app/static/app.js").read_text(encoding="utf-8")
    css = (ROOT / "laufapp/app/static/assets/v0223.css").read_text(encoding="utf-8")
    index = (ROOT / "laufapp/app/static/index.html").read_text(encoding="utf-8")
    sw = (ROOT / "laufapp/app/static/sw.js").read_text(encoding="utf-8")
    for text in [
        "Mit KI analysieren",
        "Dazu Coach fragen",
        "Erneut analysieren",
        "Keine GPS-Rohkoordinaten",
        "api/coach/runs/${id}/analysis",
    ]:
        assert text in js
    assert ".run-ai-analysis" in css and "@media(max-width:360px)" in css
    assert "assets/v0223.css?v=0.2.23" in index
    assert "app.js?v=0.2.24" in index
    assert "laufapp-v0.2.24" in sw and "assets/v0223.css?v=0.2.23" in sw
