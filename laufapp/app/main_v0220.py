"""Laufapp v0.2.20 visual brand icon release.

This composition layer preserves the complete v0.2.19 application, training,
HAE, Nabu Casa, Ingress and security behavior while updating only release
metadata and the static brand/PWA icon assets.
"""
from __future__ import annotations

import main_v0219 as previous

APP_VERSION = "0.2.20"

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
