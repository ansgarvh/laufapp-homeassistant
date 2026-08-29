"""Laufapp v0.2.1 hotfix entry point.

Keep the mature v0.2.0 API/planner wiring intact and override only release-version
metadata. This avoids a broad rewrite of main_v020.py for a small regression fix.
"""

import main_v020 as previous

APP_VERSION = "0.2.1"

# Functions defined in legacy/main_v020 resolve these module globals at runtime.
previous.APP_VERSION = APP_VERSION
previous.db_module.APP_VERSION = APP_VERSION
previous.legacy.APP_VERSION = APP_VERSION
previous.legacy.app.version = APP_VERSION
previous.training.VERSION = APP_VERSION

app = previous.app
