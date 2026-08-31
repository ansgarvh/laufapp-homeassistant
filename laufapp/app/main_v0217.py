"""Laufapp v0.2.17 transparent performance-profile release.

Replaces the legacy opaque five-bar heuristic with an evidence-informed,
self-explaining profile while preserving the v0.2.16 activity-linking,
security, HAE and compatibility stack.
"""
from __future__ import annotations

import main_v0216 as previous
import training as legacy_training
from performance_profile_v0217 import performance_profile

APP_VERSION = "0.2.17"

_module = previous
for _ in range(24):
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

# training_v020.dashboard keeps a module reference named `base` to training.py.
# Replacing this one function at v0.2.17 startup keeps the older release chain
# intact on disk while routing the active app to the richer profile calculation.
legacy_training.performance_profile = performance_profile

process_health_auto_export_request = previous.process_health_auto_export_request
app = previous.app
