"""Laufapp v0.2.25 detailed completed-run view release.

Adds a bounded, local-only response for the post-run detail screen while
preserving the v0.2.24 planning, AI, Health Auto Export and ingress stack.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import HTMLResponse

import main_v0224 as previous
from db import db_conn
from run_detail_v0225 import build_run_detail

APP_VERSION = "0.2.25"
_module = previous
for _ in range(32):
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


# v0.2.24's index contains a deliberately embedded PNG header asset. Rewriting
# that large file for two extra references would make this release unnecessarily
# regression-prone. Keep the established index byte-for-byte and compose the two
# same-origin v0.2.25 assets at the existing root response boundary instead.
_STATIC = Path(__file__).resolve().parent / "static"
_INDEX_V0225 = (_STATIC / "index.html").read_text(encoding="utf-8")
_INDEX_V0225 = _INDEX_V0225.replace(
    "</head>",
    '<link rel="stylesheet" href="assets/v0225.css?v=0.2.25"></head>',
    1,
).replace(
    "</body>",
    '<script src="assets/v0225.js?v=0.2.25" defer></script></body>',
    1,
)
app.router.routes[:] = [
    route
    for route in app.router.routes
    if not (
        getattr(route, "path", None) == "/"
        and "GET" in (getattr(route, "methods", set()) or set())
    )
]


@app.get("/")
def root_v0225():
    return HTMLResponse(
        _INDEX_V0225,
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/api/v2/runs/{rid}/detail-view")
def api_v2_run_detail_view(rid: int):
    with db_conn() as c:
        try:
            return build_run_detail(c, rid)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
