"""Laufapp v0.2.11 large Home Assistant webhook relay release entry point.

Keeps the v0.2.10 Laufapp gateway, Home Assistant Ingress compatibility,
training, persistence, Apple Health import, and security behavior unchanged.
v0.2.11 adds the companion Home Assistant custom integration that bypasses the
Home Assistant 262144-character automation-template ceiling for detailed HAE
payloads; the Laufapp application path itself remains unchanged.
"""

from __future__ import annotations

import main_v0210 as previous

APP_VERSION = "0.2.11"

_module = previous
for _ in range(15):
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
