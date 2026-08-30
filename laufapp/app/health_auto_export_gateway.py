"""Minimal Health Auto Export gateway for private and relayed sync.

The main Laufapp UI remains Home-Assistant-Ingress-only. This process exposes
only health/write endpoints on port 8100. Home Assistant can forward HAE JSON to
the dedicated ``/home-assistant-relay`` endpoint over the Supervisor-internal
app network; the same strong Laufapp token is required on that internal hop.
"""

from fastapi import FastAPI, Header, Request

from main_v0212 import APP_VERSION, process_health_auto_export_request

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


@app.post("/home-assistant-relay")
async def home_assistant_relay(
    request: Request,
    x_laufapp_token: str | None = Header(default=None, alias="X-Laufapp-Token"),
):
    """Receive JSON relayed by Home Assistant from Nabu Casa remote access.

    The public webhook credential is deliberately not accepted as Laufapp
    authentication. Home Assistant must add the separate strong Laufapp token
    on this internal hop. Bearer authentication is intentionally not exposed on
    this dedicated route so the documented relay has one unambiguous contract.
    """
    result = await process_health_auto_export_request(request, None, x_laufapp_token)
    print(
        "LAUFAPP_HAE_RELAY_OK transport=nabu_casa "
        f"runs_added={int(result.get('runs_added', 0))} "
        f"runs_existing={int(result.get('runs_existing', 0))} "
        f"samples_added={int(result.get('samples_added', 0))} "
        f"gps_points_added={int(result.get('gps_points_added', 0))} "
        f"health_metrics_added={int(result.get('health_metrics_added', 0))}",
        flush=True,
    )
    return result
