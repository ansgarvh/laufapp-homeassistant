"""Laufapp v0.2.8 diagnostics and runtime-observability entry point.

Adds persistent Apple Health import diagnostics and suppresses high-frequency
healthcheck access-log noise without changing training, persistence, Ingress, or
Health Auto Export security behavior from v0.2.7.
"""

from __future__ import annotations

import logging

from fastapi import Query

import main_v027 as previous
from import_jobs import job_diagnostics

APP_VERSION = "0.2.8"

# Propagate release metadata through the compatibility stack exactly as the
# previous release entry point does. Functional behavior remains inherited.
_module = previous
for _ in range(10):
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

# Compatibility export used by the separate minimal Health Auto Export gateway.
process_health_auto_export_request = previous.process_health_auto_export_request


class _HealthcheckAccessFilter(logging.Filter):
    """Drop only successful high-frequency health-poll Uvicorn access lines."""

    _paths = {"/api/health", "/health"}

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 5:
            path = str(args[2]).split("?", 1)[0]
            try:
                status = int(args[4])
            except (TypeError, ValueError):
                status = 500
            if path in self._paths and status < 400:
                return False
        return True


_access_logger = logging.getLogger("uvicorn.access")
if not any(isinstance(f, _HealthcheckAccessFilter) for f in _access_logger.filters):
    _access_logger.addFilter(_HealthcheckAccessFilter())

app = previous.app


@app.get("/api/apple-health/import-jobs/{job_id}/diagnostics")
def api_health_import_job_diagnostics(
    job_id: int,
    limit: int = Query(default=200, ge=1, le=500),
):
    """Return persistent phase/error diagnostics for one Apple Health import."""
    return job_diagnostics(job_id, limit)
