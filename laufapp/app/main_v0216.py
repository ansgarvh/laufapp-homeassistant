"""Laufapp v0.2.16 activity-linking release.

Adds asymmetric distance-aware automatic workout matching and explicit manual
run-to-plan linking while preserving the v0.2.15 UI/security/HAE stack.
"""
from __future__ import annotations

from fastapi import HTTPException
import main_v0215 as previous
from db import db_conn
import training as activity_matching

APP_VERSION = "0.2.16"
_module = previous
for _ in range(22):
    if _module is None: break
    if hasattr(_module, "APP_VERSION"): _module.APP_VERSION = APP_VERSION
    _module = getattr(_module, "previous", None)
core = previous.core
core.db_module.APP_VERSION = APP_VERSION
core.legacy.APP_VERSION = APP_VERSION
core.legacy.app.version = APP_VERSION
core.training.VERSION = APP_VERSION
process_health_auto_export_request = previous.process_health_auto_export_request
app = previous.app

@app.get('/api/runs/{rid}/link-candidates')
def api_run_link_candidates(rid:int):
    with db_conn() as c:
        try:return activity_matching.run_link_info(c,rid)
        except KeyError as e:raise HTTPException(404,str(e)) from e

@app.post('/api/runs/{rid}/link-workout/{wid}')
def api_run_link_workout(rid:int,wid:int):
    with db_conn() as c:
        try:return {'ok':True,'workout':activity_matching.link_run_to_workout(c,rid,wid)}
        except KeyError as e:raise HTTPException(404,str(e)) from e
        except ValueError as e:raise HTTPException(409,str(e)) from e
