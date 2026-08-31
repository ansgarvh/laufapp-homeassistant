"""Laufapp v0.2.18 multi-race planning and race-entry UX release.

Extends the existing A/B race calendar with C races, chronological A-race
handover, post-A recovery/transition handling, German decimal distance input and
an explicit race-kind selector while preserving the v0.2.17 performance profile,
activity linking, security and Health Auto Export stack.
"""
from __future__ import annotations

import main_v0217 as previous

APP_VERSION = "0.2.18"

_module = previous
for _ in range(28):
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
