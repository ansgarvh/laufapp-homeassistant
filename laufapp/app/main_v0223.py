"""Laufapp v0.2.23 OpenAI chat and per-run feedback.

This composition layer preserves the complete v0.2.22 calendar, sync, Health
Auto Export, Ingress, relay and persistence behaviour.  It replaces only the
coach callables and adds dedicated cached-analysis endpoints for one run.
"""
from __future__ import annotations

from fastapi import HTTPException, Query

import coach_v0223
import main_v0222 as previous
from db import db_conn

APP_VERSION = "0.2.23"

_module = previous
for _ in range(40):
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

# Existing mature routes resolve these main.py globals dynamically.  Rebinding
# keeps backwards-compatible URLs while activating the v0.2.23 implementation.
core.legacy.coach_chat = coach_v0223.coach_chat
core.legacy.analyze_run = coach_v0223.analyze_run


@app.get("/api/coach/runs/{rid}/analysis")
def api_v023_run_analysis_get(rid: int):
    with db_conn() as c:
        try:
            return coach_v0223.get_run_analysis(c, rid)
        except KeyError as e:
            raise HTTPException(404, str(e)) from e


@app.post("/api/coach/runs/{rid}/analysis")
def api_v023_run_analysis_post(
    rid: int, force: bool = Query(default=False)
):
    with db_conn() as c:
        try:
            return coach_v0223.analyze_run(c, rid, force=force)
        except KeyError as e:
            raise HTTPException(404, str(e)) from e
        except RuntimeError as e:
            raise HTTPException(400, str(e)) from e
