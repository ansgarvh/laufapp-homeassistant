"""Laufapp v0.2.12 real Health Auto Export workout compatibility.

Keeps the v0.2.11 large-payload Home Assistant relay, Ingress security,
training, persistence and historical Apple Health import unchanged. v0.2.12
adds a narrow compatibility layer for real localized HAE v2 running payloads
and active-energy time-series fallback.
"""

from __future__ import annotations

import health_auto_export_v0212 as hae
import main_v0211 as previous

APP_VERSION = "0.2.12"

_module = previous
for _ in range(16):
    if _module is None:
        break
    if hasattr(_module, "APP_VERSION"):
        _module.APP_VERSION = APP_VERSION
    # process_health_auto_export_request was introduced in main_v027 and
    # resolves its module-level ``hae`` reference at request time. Replacing
    # only that parser reference preserves all existing auth/body/security code.
    if hasattr(_module, "process_health_auto_export_request") and hasattr(_module, "hae"):
        _module.hae = hae
    _module = getattr(_module, "previous", None)

core = previous.core
core.db_module.APP_VERSION = APP_VERSION
core.legacy.APP_VERSION = APP_VERSION
core.legacy.app.version = APP_VERSION
core.training.VERSION = APP_VERSION

process_health_auto_export_request = previous.process_health_auto_export_request
app = previous.app
