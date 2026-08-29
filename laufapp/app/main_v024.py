"""Laufapp v0.2.4 entry point.

Adds 24-month personal-best anchors and Apple Health best-effort detection while
keeping the tested v0.2.3 API, database schema and UI intact.
"""

import health_import
import import_jobs
import main_v023 as previous
from db import db_conn
from performance_marks_v024 import (
    AUTO_SOURCE,
    detect_apple_health_best_efforts,
    install,
    sync_apple_health_best_marks,
)

APP_VERSION = "0.2.4"

# Propagate release metadata through the compatibility stack.
previous.APP_VERSION = APP_VERSION
previous.previous.APP_VERSION = APP_VERSION
previous.previous.previous.APP_VERSION = APP_VERSION
previous.previous.previous.previous.APP_VERSION = APP_VERSION
core = previous.previous.previous.previous
core.db_module.APP_VERSION = APP_VERSION
core.legacy.APP_VERSION = APP_VERSION
core.legacy.app.version = APP_VERSION
core.training.VERSION = APP_VERSION

app = previous.app
# Performance predictions and the v0.1.x API use the original training module;
# the v0.2 planner wraps it for plan generation. Patch the original module so
# every existing caller sees the same performance-anchor behavior.
install(core.legacy_training, health_import, import_jobs)


@app.get("/api/v2/performance-marks")
def api_v2_performance_marks():
    """Return user-entered and Apple-detected PB anchors without changing data."""
    with db_conn() as c:
        stored = [dict(r) for r in c.execute(
            "SELECT * FROM performance_marks ORDER BY mark_date DESC,id DESC"
        ).fetchall()]
        detected = detect_apple_health_best_efforts(c, core.legacy_training, 24)
        return {
            "stored": stored,
            "detected": detected,
            "auto_source": AUTO_SOURCE,
        }


@app.post("/api/v2/performance-marks/sync-apple-health")
def api_v2_performance_marks_sync():
    """Explicitly refresh auto-generated marks from already imported runs."""
    with db_conn() as c:
        count = sync_apple_health_best_marks(c, core.legacy_training, 24)
        predictions = core.legacy_training.predict_all(c)
        return {"ok": True, "detected": count, "predictions": predictions}
