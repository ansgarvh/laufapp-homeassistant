from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ai_settings_are_editable_without_marking_plan_stale(setup_client):
    initial = setup_client.get("/api/settings")
    assert initial.status_code == 200
    assert initial.json()["coach_model"] == "gpt-5.6-terra"
    assert initial.json()["vision_model"] == "gpt-5.6-luna"

    changed = setup_client.patch(
        "/api/settings",
        json={
            "coach_model": "gpt-5.6-sol",
            "vision_model": "gpt-5.6-terra",
            "monthly_ai_budget_eur": 12.5,
            "evidence_search": False,
        },
    )
    assert changed.status_code == 200, changed.text
    settings = changed.json()
    assert settings["coach_model"] == "gpt-5.6-sol"
    assert settings["vision_model"] == "gpt-5.6-terra"
    assert settings["monthly_ai_budget_eur"] == 12.5
    assert settings["evidence_search"] is False
    assert settings["plan_stale"] is False

    assert setup_client.patch(
        "/api/settings", json={"coach_model": "unknown-model"}
    ).status_code == 422
    assert setup_client.patch(
        "/api/settings", json={"monthly_ai_budget_eur": 0.1}
    ).status_code == 422


def test_more_exposes_ai_privacy_settings_without_api_key_in_browser():
    js = (ROOT / "laufapp/app/static/app.js").read_text(encoding="utf-8")
    css = (ROOT / "laufapp/app/static/assets/v0224.css").read_text(encoding="utf-8")
    index = (ROOT / "laufapp/app/static/index.html").read_text(encoding="utf-8")
    sw = (ROOT / "laufapp/app/static/sw.js").read_text(encoding="utf-8")
    for text in [
        "KI & Datenschutz",
        "Coach-Modell",
        "Screenshot-Modell",
        "Monatliches Budget",
        "Wissenschaftliche Websuche",
        "Keine GPS-Rohkoordinaten",
        "store=false",
        "KI-Einstellungen speichern",
    ]:
        assert text in js
    assert 'name="openai_api_key"' not in js
    assert "api('api/settings',{method:'PATCH'" in js
    assert ".ai-settings-entry" in css and "@media(max-width:360px)" in css
    assert "assets/v0224.css?v=0.2.24" in index
    assert "app.js?v=0.2.24" in index
    assert "laufapp-v0.2.24" in sw
    assert "assets/v0224.css?v=0.2.24" in sw
