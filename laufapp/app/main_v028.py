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


class _HealthcheckAccessFilter(logging.Filter):
    """Drop only successful health-poll request lines from Uvicorn access logs.

    The filter deliberately leaves application errors and every non-health API
    request untouched. Uvicorn supplies the request path as the third formatting
    argument; the message fallback keeps the behavior robust across minor Uvicorn
    logging-format changes.
    """

    _paths = {"/api/health", "/health"}

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3:
            path = str(args[2]).split("?", 1)[0]
            if path in self._paths:
                return False
        message = record.getMessage()
        return not any(f" {path} " in message for path in self._paths)


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
