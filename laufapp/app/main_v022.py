"""Laufapp v0.2.2 entry point.

Keep the tested v0.2.1 API/training stack intact and harden delivery of frontend
assets for Home Assistant/iOS. Settings extensions (A/B races and planner
aggressiveness) live in versioned assets and must never be served stale after an
add-on update.
"""

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import main_v021 as previous

APP_VERSION = "0.2.2"

previous.APP_VERSION = APP_VERSION
previous.previous.APP_VERSION = APP_VERSION
previous.previous.db_module.APP_VERSION = APP_VERSION
previous.previous.legacy.APP_VERSION = APP_VERSION
previous.previous.legacy.app.version = APP_VERSION
previous.previous.training.VERSION = APP_VERSION

app = previous.app
STATIC = previous.previous.legacy.STATIC

# v0.2.x assets are physically stored below static/assets. The legacy mount used
# the static root itself, which made /assets/v020.js resolve to static/v020.js
# and therefore return 404. This is why A/B races, science UI and planner
# aggressiveness were present in the repository but invisible in the real app.
for route in app.routes:
    if getattr(route, "path", None) == "/assets":
        route.app = StaticFiles(directory=STATIC / "assets")
        break


@app.get("/bugfix.css")
def bugfix_css():
    return FileResponse(STATIC / "bugfix.css", media_type="text/css", headers={"Cache-Control": "no-store, max-age=0"})


@app.middleware("http")
async def frontend_cache_control(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if (
        path == "/"
        or path.endswith("/index.html")
        or path.endswith("/app.js")
        or path.endswith("/styles.css")
        or path.endswith("/bugfix.css")
        or path.endswith("/sw.js")
        or "/assets/" in path
    ):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response
