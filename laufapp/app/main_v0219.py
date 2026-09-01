"""Laufapp v0.2.19 manual-completion undo release.

Adds a safe reversible manual workout-completion state while preserving linked
run authority and the complete v0.2.18 multi-race/security/HAE stack.
"""
from __future__ import annotations

import main_v0218 as previous

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
