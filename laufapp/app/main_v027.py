"""Laufapp v0.2.7 security-hardening entry point.

Hardens the v0.2.6 Health Auto Export interface and the Home Assistant Ingress
trust boundary without changing persistent data or training behavior.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os

from fastapi import Header, HTTPException, Request
from fastapi.responses import JSONResponse

import health_auto_export_v027 as hae
import health_import_hardening_v027 as health_import_hardening
import main_v026 as previous
from db import db_conn
from performance_marks_v024 import sync_apple_health_best_marks

APP_VERSION = "0.2.7"
REQUEST_BODY_TIMEOUT_SECONDS = 120
HOME_ASSISTANT_INTERNAL_NETWORK = ipaddress.ip_network("172.30.32.0/23")
HOME_ASSISTANT_INGRESS_PROXY = ipaddress.ip_address("172.30.32.2")

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

# The existing background-import function resolves these module globals at run
# time, so installing the narrow wrappers also protects queued/retried imports
# without replacing the tested import-job machinery.
health_import_hardening.install()

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


def _client_ip(request: Request):
    host = request.client.host if request.client else ""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def _trusted_ingress_compat_request(request: Request) -> bool:
    """Allow authenticated HA Ingress from the internal Supervisor network.

    Home Assistant documents 172.30.32.2 as the normal Ingress proxy. Some real
    installations can nevertheless present another peer from the internal
    172.30.32.0/23 network while preserving authenticated Ingress headers. The
    compatibility path therefore requires BOTH an internal HA peer and headers
    that are only expected on an authenticated Ingress request. External clients
    cannot bypass the guard by forging those headers alone.
    """
    peer = _client_ip(request)
    if peer is None or peer not in HOME_ASSISTANT_INTERNAL_NETWORK:
        return False
    ingress_path = request.headers.get("x-ingress-path", "")
    remote_user = request.headers.get("x-remote-user-id", "")
    hass_source = request.headers.get("x-hass-source", "")
    authenticated_marker = bool(remote_user) or hass_source == "core.ingress"
    return ingress_path.startswith("/api/hassio_ingress/") and authenticated_marker


@app.middleware("http")
async def strict_home_assistant_ingress_boundary(request: Request, call_next):
    """Keep port 8099 Ingress-only while tolerating HA-internal proxy variants."""
    if os.environ.get("LAUFAPP_TRUSTED_INGRESS_ONLY") == "1":
        peer = _client_ip(request)
        host = request.client.host if request.client else ""
        if host in {"127.0.0.1", "::1"}:
            if request.url.path != "/api/health":
                print(
                    f"LAUFAPP_INGRESS_BLOCKED peer={host or 'unknown'} path={request.url.path} reason=loopback_non_health",
                    flush=True,
                )
                return JSONResponse(
                    {"detail": "Direkter Zugriff ist deaktiviert. Bitte Home Assistant Ingress verwenden."},
                    status_code=403,
                )
        elif peer == HOME_ASSISTANT_INGRESS_PROXY:
            pass
        elif _trusted_ingress_compat_request(request):
            pass
        else:
            print(
                "LAUFAPP_INGRESS_BLOCKED "
                f"peer={host or 'unknown'} path={request.url.path} "
                f"internal_peer={bool(peer and peer in HOME_ASSISTANT_INTERNAL_NETWORK)} "
                f"ingress_path={bool(request.headers.get('x-ingress-path'))} "
                f"remote_user={bool(request.headers.get('x-remote-user-id'))} "
                f"hass_source={request.headers.get('x-hass-source','') or '-'}",
                flush=True,
            )
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
    try:
        async with asyncio.timeout(REQUEST_BODY_TIMEOUT_SECONDS):
            async for chunk in request.stream():
                if len(body) + len(chunk) > hae.MAX_BODY_BYTES:
                    raise HTTPException(status_code=413, detail="Health Auto Export Payload ist zu groß.")
                body.extend(chunk)
    except TimeoutError as exc:
        raise HTTPException(status_code=408, detail="Health Auto Export Upload hat das Zeitlimit überschritten.") from exc
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
