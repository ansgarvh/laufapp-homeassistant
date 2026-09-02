# Nabu Casa Health Auto Export Relay

Laufapp v0.2.13 uses a small Home Assistant custom integration to relay large Health Auto Export (HAE) JSON payloads without exposing Laufapp ports to the internet. The original raw-body relay was introduced in v0.2.11; v0.2.13 adds explicit rate, concurrency and slow-body limits.

## Why the direct relay exists

The old v0.2.10 automation path used a Home Assistant webhook trigger followed by:

```yaml
payload: "{{ trigger.json | to_json }}"
```

Detailed running workouts with second-level metrics can exceed Home Assistant's 262144-character template-output limit. In a real installation this caused `Template output exceeded maximum size of 262144 characters` before `rest_command` could run. The dedicated `hooks.nabu.casa` cloudhook path also returned HTTP 413 for the same large HAE request in that installation.

The current path avoids both layers. It uses the normal Nabu Casa Remote UI HTTPS address and a custom Home Assistant webhook handler that reads the request body directly and forwards the raw JSON to Laufapp.

## Transport architecture

```text
iPhone / Health Auto Export
    -> HTTPS
https://<remote-id>.ui.nabu.casa/api/webhook/<secret-webhook-id>
    -> Home Assistant webhook API
custom_components/laufapp_hae_relay
    -> raw JSON, no Jinja/rest_command serialization
http://c87ed7df-laufapp:8100/home-assistant-relay
    -> strong X-Laufapp-Token
Laufapp hardened HAE ingest
```

The final HTTP hop stays inside the Home Assistant Supervisor app network. Port 8100 remains unpublished (`null`) in Laufapp's app configuration. Do not forward ports 8099 or 8100 on the internet router.

## Security properties

- The public URL is Home Assistant's Nabu Casa Remote UI HTTPS endpoint plus a long random webhook ID. Treat the complete URL and webhook ID like a password.
- The webhook accepts POST only and `application/json` only.
- The custom integration never embeds the Laufapp token in the public HAE request. Home Assistant adds the existing strong `health_auto_export_token` only on the internal Home Assistant -> Laufapp hop.
- The internal destination is fixed in code to `http://c87ed7df-laufapp:8100/home-assistant-relay`; it is not user-configurable, so the component cannot become an arbitrary HTTP proxy.
- Body size is limited to 16 MiB before forwarding.
- Reading the public request body is limited to 120 seconds.
- At most 12 webhook requests per 60 seconds are accepted by one running integration instance.
- At most three requests are forwarded concurrently; excess load is rejected with HTTP 429 after a short wait.
- Laufapp applies its own authentication, JSON, body-size, timeout, workout/point limits and idempotent import checks again on the internal endpoint.
- Request bodies, webhook IDs and tokens are not written to normal relay logs.
- The Laufapp UI remains Home Assistant Ingress-only on port 8099.
- Laufapp v0.2.13 no longer receives the unrelated Home Assistant `/share` mount.

## 1. Install the Home Assistant custom integration

Copy this repository folder:

```text
custom_components/laufapp_hae_relay/
```

into Home Assistant so the final paths are:

```text
/config/custom_components/laufapp_hae_relay/__init__.py
/config/custom_components/laufapp_hae_relay/manifest.json
```

The integration has no third-party Python requirements; it uses Home Assistant's built-in webhook and HTTP client APIs.

## 2. Configure secrets

Keep the existing strong Laufapp token in `secrets.yaml` and add/use a separate webhook ID secret:

```yaml
laufapp_health_auto_export_token: "COPY_THE_EXISTING_LAUFAPP_TOKEN_HERE"
laufapp_hae_webhook_id: "COPY_THE_EXISTING_OR_NEW_RANDOM_WEBHOOK_ID_HERE"
```

The webhook ID must be 32-256 characters and contain only letters, digits, `_` or `-`. Do not publish either secret.

## 3. Configure the relay integration

Merge `home_assistant/laufapp_hae_relay_configuration.yaml.example` into `/config/configuration.yaml`:

```yaml
laufapp_hae_relay:
  webhook_id: !secret laufapp_hae_webhook_id
  token: !secret laufapp_health_auto_export_token
```

Before restarting Home Assistant, remove or disable any old webhook automation that uses the same webhook ID. Home Assistant permits only one handler per webhook ID; the custom integration deliberately fails closed if the ID is already registered.

The old `rest_command.laufapp_health_auto_export_relay` is not required and should be removed if it is still present. The obsolete Automation-/`rest_command` example files were removed from the repository in v0.2.13.

Validate the Home Assistant configuration and restart Home Assistant.

## 4. Health Auto Export URL

Use Home Assistant Cloud's Remote UI URL, not the dedicated `https://hooks.nabu.casa/...` cloudhook URL.

If Remote UI is:

```text
https://example.ui.nabu.casa
```

and the secret webhook ID is `YOUR_WEBHOOK_ID`, the HAE target is:

```text
https://example.ui.nabu.casa/api/webhook/YOUR_WEBHOOK_ID
```

Do not add `X-Laufapp-Token` or the Laufapp token to Health Auto Export. The public credential is the secret webhook URL; the separate Laufapp token stays only inside Home Assistant.

## 5. Health Auto Export settings

Use REST API, JSON, Export Version 2.

For running workouts:

- Data type: Workouts / Running
- Route Data: On
- Workout Metrics: On
- Workout Metrics Time Grouping: Seconds
- Batch requests: On
- Date range: **Previous 7 Days / Letzte 7 Tage**

For recovery/health metrics, use a second HAE automation for resting heart rate, HRV, body mass, VO2max and sleep. `Previous 7 Days` is also recommended there. Current HAE JSON v2 sends these as `resting_heart_rate`, `heart_rate_variability`, `weight_body_mass`, `vo2max` and `sleep_analysis`; Laufapp v0.2.27 accepts those current identifiers as well as the older aliases. Sleep duration is calculated from Core + REM + Deep when HAE sends the current stage-based sleep shape.

## Why Previous 7 Days?

HAE and iOS background execution are not guaranteed to complete at every scheduled instant. An overlapping seven-day window resends recent data, while Laufapp's workout, sample, GPS and health-metric deduplication makes repeated delivery idempotent. This is safer than relying on a single irreversible `Since Last Sync` checkpoint.

## Verification

First verify the public webhook with a minimal request:

```bash
curl -i -X POST \
  'https://YOUR-REMOTE-ID.ui.nabu.casa/api/webhook/YOUR_WEBHOOK_ID' \
  -H 'Content-Type: application/json' \
  --data '{"data":{"workouts":[],"metrics":[]}}'
```

A successful relay should produce a 2xx response and a safe Laufapp log line beginning with:

```text
LAUFAPP_HAE_RELAY_OK transport=nabu_casa
```

Then run a real HAE workout export with route and second-level workout metrics enabled. For an already imported historical run, `runs_existing=1` is expected and missing detail samples/GPS data should be added without creating a duplicate run.

## Failure isolation

- No Home Assistant webhook handling: verify the `.ui.nabu.casa/api/webhook/...` URL and webhook ID.
- Webhook ID already registered: remove/disable the old automation using that ID and restart Home Assistant.
- HTTP 408: request body was delivered too slowly for the 120-second read limit.
- HTTP 413: request exceeds 16 MiB and must be split by HAE.
- HTTP 415: HAE is not sending `application/json`.
- HTTP 429: relay rate or concurrency limit was reached; wait and retry instead of weakening the limits.
- HTTP 502/504: Home Assistant received the request but could not reach the internal Laufapp relay; verify Laufapp is running and the strong token is configured.
- Laufapp returns 4xx: inspect Laufapp logs for the hardened HAE validation reason; do not weaken security checks to accept malformed payloads.

## Test boundary

Repository CI tests the custom relay logic in isolation, including >262144-character payloads, the 16 MiB limit, slow-body timeout, rate limiting, token/webhook validation, POST-only registration, internal Laufapp endpoint, idempotent ingestion, Docker runtime, Home Assistant network simulation and existing regressions.

A real Home Assistant OS + Nabu Casa Remote UI + iPhone Health Auto Export path cannot be executed inside repository CI and must be verified on the target installation.
