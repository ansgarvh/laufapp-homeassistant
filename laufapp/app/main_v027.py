"""Laufapp v0.2.7 security-hardening entry point.

Hardens the v0.2.6 Health Auto Export interface and the Home Assistant Ingress
trust boundary without changing persistent data or training behavior.
"""

from __future__ import annotations

import json
import os

from fastapi import Header, HTTPException, Request
from fastapi.responses import JSONResponse

import health_auto_export_v027 as hae
import main_v026 as previous
from db import db_conn
from performance_marks_v024 import sync_apple_health_best_marks

APP_VERSION = "0.2.7"

# Propagate release metadata through the existing compatibility stack.
_module = previous
for _ in range(8):
    if _module is None:
        break
    if hasattr(_module, "APP_VERSION"):
        _module.APP_VERSION = APP_VERSION
    _module = getattr(_module, "previous", None)
core = previous.core
core.db_module.APP_VERSION = APP_VERSION
core.legacy.APP_VERSION = APP_VERSION
core.legacy.app.version = APP_VERSION
core.training.VERSION = APP_VERSION

app = previous.app

# Replace only the v0.2.6 sync/status routes. The rest of the tested application
# remains untouched.
app.router.routes[:] = [
    route
    for route in app.router.routes
    if not (
        getattr(route, "path", None) in {
            "/api/v2/health-auto-export",
            "/api/v2/health-auto-export/status",
        }
    )
]


@app.middleware("http")
async def strict_home_assistant_ingress_boundary(request: Request, call_next):
    """Trust the real TCP peer, never user-controlled forwarding headers.

    Home Assistant documents 172.30.32.2 as the Ingress proxy address. Loopback
    is retained only for the container healthcheck. This remains a defense in
    depth even if somebody accidentally publishes port 8099 later.
    """
    if os.environ.get("LAUFAPP_TRUSTED_INGRESS_ONLY") == "1":
        host = request.client.host if request.client else ""
        if host in {"127.0.0.1", "::1"}:
            if request.url.path != "/api/health":
                return JSONResponse(
                    {"detail": "Direkter Zugriff ist deaktiviert. Bitte Home Assistant Ingress verwenden."},
                    status_code=403,
                )
        elif host != "172.30.32.2":
            return JSONResponse(
                {"detail": "Direkter Zugriff ist deaktiviert. Bitte Home Assistant Ingress verwenden."},
                status_code=403,
            )
    return await call_next(request)


def _require_auth(authorization: str | None, x_laufapp_token: str | None) -> None:
    problem = hae.token_configuration_error()
    if problem is not None:
        raise HTTPException(status_code=503, detail=problem)
    if not hae.authorized(authorization, x_laufapp_token):
        raise HTTPException(status_code=401, detail="Ungültige Health Auto Export Authentifizierung.")


def _is_json_content_type(value: str | None) -> bool:
    media_type = (value or "").split(";", 1)[0].strip().lower()
    return media_type == "application/json" or media_type.endswith("+json")


async def _read_limited_json(request: Request):
    if not _is_json_content_type(request.headers.get("content-type")):
        raise HTTPException(status_code=415, detail="Content-Type application/json erforderlich.")

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Ungültiger Content-Length Header.") from exc
        if declared < 0:
            raise HTTPException(status_code=400, detail="Ungültiger Content-Length Header.")
        if declared > hae.MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Health Auto Export Payload ist zu groß.")

    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > hae.MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Health Auto Export Payload ist zu groß.")
        body.extend(chunk)
    if not body:
        raise HTTPException(status_code=400, detail="Leerer Health Auto Export Payload.")
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise HTTPException(status_code=400, detail="Ungültiges JSON.") from exc


async def process_health_auto_export_request(
    request: Request,
    authorization: str | None,
    x_laufapp_token: str | None,
):
    # Authenticate before reading the request body so unauthenticated callers
    # cannot make the process buffer large Health payloads.
    _require_auth(authorization, x_laufapp_token)
    payload = await _read_limited_json(request)
    try:
        with db_conn() as c:
            result = hae.ingest(c, payload, core.legacy_training)
            # A re-delivery of an existing workout does not change its race
            # performance. Recompute PBs only when a new run was actually added.
            result["performance_marks_detected"] = (
                int(sync_apple_health_best_marks(c, core.legacy_training, 24))
                if result["runs_added"]
                else 0
            )
            c.execute(
                "INSERT INTO settings(key,value) VALUES('health_auto_export_last_result',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (json.dumps(result, ensure_ascii=False),),
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Deliberately return only ingestion metadata. The internet-facing sync
    # credential must not double as a read credential for predictions or other
    # personal Laufapp data.
    return {"ok": True, **result}


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
    token_problem = hae.token_configuration_error()
    return {
        "configured": bool(hae.configured_token()),
        "secure_token": token_problem is None,
        "token_requirement": f"mindestens {hae.MIN_TOKEN_LENGTH} zufällige Zeichen",
        "last_sync": values.get("health_auto_export_last_sync"),
        "last_result": values.get("health_auto_export_last_result"),
    }
