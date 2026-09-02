"""Laufapp v0.2.27 explicit planned-workout phases release."""

from __future__ import annotations

from pathlib import Path

from fastapi.responses import HTMLResponse

import main_v0226 as previous
import training as legacy_training
from workout_phases_v0227 import enrich_workout


APP_VERSION = "0.2.27"

_module = previous
for _ in range(48):
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


# training_v020 delegates row serialization to the original training module at
# runtime. Patching this one narrow boundary enriches both freshly generated and
# already persisted workouts while preserving all rows and planner decisions.
if not getattr(legacy_training._wdict, "_laufapp_v0227_phases", False):
    _previous_wdict = legacy_training._wdict

    def _wdict_v0227(row):
        return enrich_workout(_previous_wdict(row))

    _wdict_v0227._laufapp_v0227_phases = True
    legacy_training._wdict = _wdict_v0227


# Compose the established v0.2.25 run-detail assets with the new phase styles at
# the response boundary. The large embedded header PNG in index.html remains
# untouched.
_STATIC = Path(__file__).resolve().parent / "static"
_INDEX_V0227 = previous.previous._INDEX_V0225.replace(
    "</head>",
    '<link rel="stylesheet" href="assets/v0227.css?v=0.2.27"></head>',
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
def root_v0227():
    return HTMLResponse(
        _INDEX_V0227,
        headers={"Cache-Control": "no-cache"},
    )
