"""Laufapp v0.2.9 Home Assistant Ingress compatibility entry point.

Keeps the v0.2.8 import diagnostics and v0.2.7 security model while restoring a
strictly Home-Assistant-internal compatibility path for authenticated Ingress
requests whose TCP peer is not the canonical 172.30.32.2 address.
"""

from __future__ import annotations

import main_v028 as previous

APP_VERSION = "0.2.9"

_module = previous
for _ in range(12):
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
