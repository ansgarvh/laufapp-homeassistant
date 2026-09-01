"""Laufapp v0.2.21 inline brand icon hotfix.

This composition layer preserves the complete v0.2.20 application, training,
HAE, Nabu Casa, Ingress and security behavior. The release fixes only the
header brand icon delivery by embedding the approved icon directly in the
HTML so Home Assistant Ingress does not need a separate image request.
"""
from __future__ import annotations

import main_v0220 as previous

APP_VERSION = "0.2.21"

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
