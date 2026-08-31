"""Laufapp v0.2.13 security, cleanup and training-trend entry point.

Keeps the v0.2.12 Health Auto Export compatibility and all training/persistence
behaviour while reducing obsolete privileges/endpoints and adding bounded
progress analytics derived from the existing local database.
"""

from __future__ import annotations

import json
from typing import Literal

from fastapi import Query, Request
from fastapi.responses import JSONResponse

import main_v0212 as previous
from db import db_conn
from progress_trends_v0213 import build_training_trends

APP_VERSION = "0.2.13"

_module = previous
for _ in range(17):
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

process_health_auto_export_request = previous.process_health_auto_export_request
app = previous.app

# The repository-transfer write endpoint was a one-time bridge from the old
# local app to this GitHub app. The current installation no longer needs to
# write arbitrary backup material into Home Assistant /share. Keep the internal
# migration helpers for historical compatibility, but remove the exposed route.
# Also replace the legacy unbounded chat-history endpoint with a bounded one.
app.router.routes[:] = [
    route
    for route in app.router.routes
    if getattr(route, "path", None)
    not in {"/api/system/prepare-repository-transfer", "/api/coach/history"}
]


@app.middleware("http")
async def browser_security_hardening(request: Request, call_next):
    """Add low-risk browser hardening without changing HA Ingress embedding."""
    if (
        request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
        and request.headers.get("sec-fetch-site", "").strip().lower() == "cross-site"
    ):
        return JSONResponse(
            {"detail": "Cross-Site-Schreibzugriff abgelehnt."},
            status_code=403,
            headers={"Cache-Control": "no-store"},
        )

    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; "
        "base-uri 'self'; form-action 'self'",
    )
    return response


@app.get("/api/coach/history")
def api_chat_history(limit: int = Query(default=40, ge=1, le=200)):
    with db_conn() as c:
        out = []
        records = c.execute(
            "SELECT * FROM chat_messages ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        for row in reversed(records):
            item = dict(row)
            try:
                item["meta"] = json.loads(item.pop("meta_json"))
            except (TypeError, ValueError, json.JSONDecodeError):
                item["meta"] = {}
            out.append(item)
        return out


@app.get("/api/progress/trends")
def api_progress_trends(
    period: Literal["3m", "6m", "12m", "24m"] = "6m",
):
    with db_conn() as c:
        return build_training_trends(c, period)
