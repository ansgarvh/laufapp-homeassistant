"""Laufapp v0.2.18 multi-race calendar release.

Adds A/B/C race priorities, race-to-race recovery transitions and a hard
history boundary: race-calendar changes may replan only today and the future.
The v0.2.17 performance profile, v0.2.16 activity linking, HAE and security
stack remain unchanged.
"""
from __future__ import annotations

import main_v0217 as previous

APP_VERSION = "0.2.18"

_module = previous
for _ in range(26):
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
