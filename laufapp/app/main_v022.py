"""Laufapp v0.2.2 entry point.

Keep the tested v0.2.1 API/training stack intact and harden delivery of frontend
assets for Home Assistant/iOS. Settings extensions (A/B races and planner
aggressiveness) live in versioned assets and must never be served stale after an
add-on update.
"""

import main_v021 as previous

APP_VERSION = "0.2.2"

previous.APP_VERSION = APP_VERSION
previous.previous.APP_VERSION = APP_VERSION
previous.previous.db_module.APP_VERSION = APP_VERSION
previous.previous.legacy.APP_VERSION = APP_VERSION
previous.previous.legacy.app.version = APP_VERSION
previous.previous.training.VERSION = APP_VERSION

app = previous.app


@app.middleware("http")
async def frontend_cache_control(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if (
        path == "/"
        or path.endswith("/index.html")
        or path.endswith("/app.js")
        or path.endswith("/styles.css")
        or path.endswith("/sw.js")
        or "/assets/" in path
    ):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response
