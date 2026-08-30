"""Minimal Health Auto Export gateway for optional VPN/HTTPS exposure.

The main Laufapp UI remains Home-Assistant-Ingress-only. This process exposes
only a health endpoint and the authenticated HAE ingest endpoint on port 8100.
"""

from fastapi import FastAPI, Header, Request

from main_v029 import APP_VERSION, process_health_auto_export_request

app = FastAPI(
    title="Laufapp Health Sync Gateway",
    version=APP_VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/health")
def health():
    # Do not disclose the application version on the separately reachable port.
    return {"ok": True}


@app.post("/health-auto-export")
async def health_auto_export(
    request: Request,
    authorization: str | None = Header(default=None),
    x_laufapp_token: str | None = Header(default=None, alias="X-Laufapp-Token"),
):
    return await process_health_auto_export_request(request, authorization, x_laufapp_token)
