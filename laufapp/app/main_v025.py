"""Laufapp v0.2.5 entry point.

Adds visible PB presentation, compact mobile navigation assets and a bounded
post-PB training progression signal on top of the tested v0.2.4 stack.
"""

import main_v024 as previous
from performance_marks_v025 import install

APP_VERSION = "0.2.5"

previous.APP_VERSION = APP_VERSION
previous.previous.APP_VERSION = APP_VERSION
previous.previous.previous.APP_VERSION = APP_VERSION
previous.previous.previous.previous.APP_VERSION = APP_VERSION
previous.previous.previous.previous.previous.APP_VERSION = APP_VERSION
core = previous.core
core.db_module.APP_VERSION = APP_VERSION
core.legacy.APP_VERSION = APP_VERSION
core.legacy.app.version = APP_VERSION
core.training.VERSION = APP_VERSION

app = previous.app
install(core.legacy_training, core.legacy_training)
