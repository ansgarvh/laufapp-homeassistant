"""Minimal Health Auto Export gateway for optional LAN/VPN exposure.

The main Laufapp UI remains Home-Assistant-Ingress-only. This process exposes
only a health endpoint and the authenticated HAE ingest endpoint on port 8100.
"""

from fastapi import FastAPI, Header, Request

from main_v026 import APP_VERSION, process_health_auto_export_request

app = FastAPI(title="Laufapp Health Sync Gateway", version=APP_VERSION, docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
def health():
    return {"ok": True, "version": APP_VERSION}


@app.post("/health-auto-export")
async def health_auto_export(
    request: Request,
    authorization: str | None = Header(default=None),
    x_laufapp_token: str | None = Header(default=None, alias="X-Laufapp-Token"),
):
    return await process_health_auto_export_request(request, authorization, x_laufapp_token)
