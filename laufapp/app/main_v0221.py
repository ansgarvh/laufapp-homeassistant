"""Laufapp v0.2.21 brand icon delivery fix.

This composition layer preserves the complete v0.2.20 application, training,
HAE, Nabu Casa, Ingress and security behavior while exposing the approved
brand icon files on the top-level URLs used by the browser/PWA.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse

import main_v0220 as previous

APP_VERSION = "0.2.21"

_module = previous
for _ in range(30):
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
STATIC = Path(__file__).resolve().parent / "static"


@app.get("/icon-192.png", include_in_schema=False)
def brand_icon_192():
    return FileResponse(
        STATIC / "icon-192.png",
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/icon-512.png", include_in_schema=False)
def brand_icon_512():
    return FileResponse(
        STATIC / "icon-512.png",
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
