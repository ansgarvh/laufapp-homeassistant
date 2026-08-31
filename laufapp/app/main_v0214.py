"""Laufapp v0.2.14 UI release entry point.

Keeps the fully tested v0.2.13 security/HAE stack unchanged while exposing
the v0.2.14 release version for the focused weekly-overview UI update.
"""

from __future__ import annotations

import main_v0213 as previous

APP_VERSION = "0.2.14"

_module = previous
for _ in range(18):
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
