"""Laufapp v0.2.19 manual-completion undo release.

Adds a safe reversible manual workout-completion state while preserving linked
run authority and the complete v0.2.18 multi-race/security/HAE stack.
"""
from __future__ import annotations

from fastapi import HTTPException

import main_v0218 as previous
from db import db_conn

APP_VERSION = "0.2.19"

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
StatusPayload = core.legacy.StatusPayload

# Replace only the mature status route at the v0.2.19 composition layer. Keeping
# main.py unchanged preserves the long-lived API/security baseline and avoids
# shifting line-based security exceptions for unrelated legacy code.
for _route in list(app.router.routes):
    if getattr(_route, "path", None) == "/api/workouts/{wid}/status" and "POST" in getattr(_route, "methods", set()):
        app.router.routes.remove(_route)


@app.post('/api/workouts/{wid}/status')
def api_workout_status_v0219(wid:int,p:StatusPayload):
    with db_conn() as c:
        workout=c.execute("SELECT id,status,linked_run_id FROM workouts WHERE id=?",(wid,)).fetchone()
        if not workout:
            raise HTTPException(404,'Training nicht gefunden.')
        if workout['linked_run_id'] is not None:
            if p.status!='completed':
                raise HTTPException(409,'Diese Einheit ist mit einem Lauf verknüpft. Löse zuerst die Aktivitätsverknüpfung, bevor der Abschlussstatus geändert wird.')
            return {'ok':True}
        c.execute("UPDATE workouts SET status=?,manual_override=1,modified_by='user' WHERE id=?",(p.status,wid))
        return {'ok':True}
