"""Laufapp v0.2.26 Health Auto Export recovery-metrics release."""

from __future__ import annotations

import health_auto_export_v0226 as hae
import main_v0225 as previous


APP_VERSION = "0.2.26"

_module = previous
for _ in range(40):
    if _module is None:
        break
    if hasattr(_module, "APP_VERSION"):
        _module.APP_VERSION = APP_VERSION
    # The hardened request handler resolves its module-level parser at request
    # time. Replace only that dependency; auth, body limits and relay behavior
    # remain on the established path.
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
