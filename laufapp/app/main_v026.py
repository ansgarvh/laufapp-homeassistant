"""Laufapp v0.2.6 entry point.

Adds authenticated Health Auto Export JSON v2 ingestion on top of the tested
v0.2.5 application while preserving Home Assistant Ingress for the UI.
"""

import json

from fastapi import Header, HTTPException, Request

import health_auto_export_v026 as hae
import main_v025 as previous
from db import db_conn

APP_VERSION = "0.2.6"

previous.APP_VERSION = APP_VERSION
previous.previous.APP_VERSION = APP_VERSION
previous.previous.previous.APP_VERSION = APP_VERSION
previous.previous.previous.previous.APP_VERSION = APP_VERSION
previous.previous.previous.previous.previous.APP_VERSION = APP_VERSION
previous.previous.previous.previous.previous.previous.APP_VERSION = APP_VERSION
core = previous.core
core.db_module.APP_VERSION = APP_VERSION
core.legacy.APP_VERSION = APP_VERSION
core.legacy.app.version = APP_VERSION
core.training.VERSION = APP_VERSION

app = previous.app


def _require_auth(authorization: str | None, x_laufapp_token: str | None) -> None:
    if not hae.configured_token():
        raise HTTPException(status_code=503, detail="Health Auto Export Token ist noch nicht konfiguriert.")
    if not hae.authorized(authorization, x_laufapp_token):
        raise HTTPException(status_code=401, detail="Ungültige Health Auto Export Authentifizierung.")


async def process_health_auto_export_request(
    request: Request,
    authorization: str | None,
    x_laufapp_token: str | None,
):
    _require_auth(authorization, x_laufapp_token)
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > hae.MAX_BODY_BYTES:
                raise HTTPException(status_code=413, detail="Health Auto Export Payload ist zu groß.")
        except ValueError:
            raise HTTPException(status_code=400, detail="Ungültiger Content-Length Header.")
    body = await request.body()
    if len(body) > hae.MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Health Auto Export Payload ist zu groß.")
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Ungültiges JSON.") from exc
    try:
        with db_conn() as c:
            result = hae.ingest(
                c,
                payload,
                core.legacy_training,
                previous.previous.sync_apple_health_best_marks,
            )
            predictions = core.legacy_training.predict_all(c)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "version": APP_VERSION, **result, "predictions": predictions}


@app.post("/api/v2/health-auto-export")
async def api_health_auto_export(
    request: Request,
    authorization: str | None = Header(default=None),
    x_laufapp_token: str | None = Header(default=None, alias="X-Laufapp-Token"),
):
    return await process_health_auto_export_request(request, authorization, x_laufapp_token)


@app.get("/api/v2/health-auto-export/status")
def api_health_auto_export_status():
    with db_conn() as c:
        rows = c.execute(
            "SELECT key,value FROM settings WHERE key IN ('health_auto_export_last_sync','health_auto_export_last_result')"
        ).fetchall()
    values = {r["key"]: json.loads(r["value"]) for r in rows}
    return {
        "configured": bool(hae.configured_token()),
        "last_sync": values.get("health_auto_export_last_sync"),
        "last_result": values.get("health_auto_export_last_result"),
    }
