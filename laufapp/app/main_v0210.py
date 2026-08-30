"""Laufapp v0.2.10 Nabu Casa relay entry point.

Keeps the v0.2.9 Home Assistant Ingress compatibility and all earlier import,
training, persistence, and security behavior unchanged.  v0.2.10 adds only the
separate Home Assistant/Nabu Casa transport around the existing hardened Health
Auto Export ingestion path.
"""

from __future__ import annotations

import main_v029 as previous

APP_VERSION = "0.2.10"

_module = previous
for _ in range(14):
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
