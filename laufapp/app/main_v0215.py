"""Laufapp v0.2.15 focused weekly-overview UI release.

Keeps the fully tested v0.2.14 backend/security/HAE stack unchanged while
exposing the v0.2.15 release version for deterministic week UI rendering.
"""

from __future__ import annotations

import main_v0214 as previous

APP_VERSION = "0.2.15"

_module = previous
for _ in range(20):
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
