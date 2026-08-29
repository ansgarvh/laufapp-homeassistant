"""Laufapp v0.3.0 entry point with native iOS HealthKit companion support."""
from fastapi import HTTPException, Request

import main_v025 as previous
from db import db_conn
from ios_healthkit_sync import ingest_healthkit_payload
from performance_marks_v024 import sync_apple_health_best_marks

APP_VERSION = "0.3.0"

# Keep release metadata consistent through the compatibility stack.
module = previous
while module is not None:
    if hasattr(module, "APP_VERSION"):
        module.APP_VERSION = APP_VERSION
    module = getattr(module, "previous", None)

core = previous.core
core.db_module.APP_VERSION = APP_VERSION
core.legacy.APP_VERSION = APP_VERSION
core.legacy.app.version = APP_VERSION
core.training.VERSION = APP_VERSION
app = previous.app


@app.post("/api/v3/healthkit/sync")
async def api_v3_healthkit_sync(request: Request):
    """Ingest a native HealthKit payload through the existing HA ingress path."""
    try:
        payload = await request.json()
        with db_conn() as c:
            stats = ingest_healthkit_payload(
                c,
                payload,
                core.legacy_training,
                sync_apple_health_best_marks,
            )
        return {"ok": True, "version": APP_VERSION, **stats}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v3/healthkit/status")
def api_v3_healthkit_status():
    with db_conn() as c:
        latest = c.execute(
            "SELECT id,started_at,distance_km,duration_s FROM runs "
            "WHERE source='apple_health_live' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        live_runs = c.execute(
            "SELECT COUNT(*) FROM runs WHERE source='apple_health_live'"
        ).fetchone()[0]
        live_samples = c.execute(
            "SELECT COUNT(*) FROM run_samples WHERE source='apple_health_live'"
        ).fetchone()[0]
    return {
        "ok": True,
        "connected_source": "native_healthkit",
        "live_runs": int(live_runs),
        "live_samples": int(live_samples),
        "latest_run": dict(latest) if latest else None,
    }
