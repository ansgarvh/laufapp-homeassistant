# Nabu Casa Health Auto Export Relay

Laufapp v0.2.10 supports a Home-Assistant-internal relay for Health Auto Export (HAE). The iPhone sends JSON to a Nabu Casa cloud webhook over HTTPS. Home Assistant receives that webhook and forwards the JSON only over the Supervisor-internal app network to Laufapp.

## Transport architecture

```text
iPhone / Health Auto Export
    -> HTTPS
Nabu Casa cloud webhook (secret webhook ID)
    -> Home Assistant webhook automation
Home Assistant REST command
    -> http://c87ed7df-laufapp:8100/home-assistant-relay
Laufapp hardened HAE ingest
```

The final HTTP hop is unencrypted because it never leaves the Home Assistant internal container network. Port 8100 remains `null` in Laufapp's app configuration and does not need a host/router port mapping for this mode.

## Security properties

- The public endpoint is the Nabu Casa `https://hooks.nabu.casa/...` cloudhook, not Laufapp port 8100.
- Treat the random webhook ID/cloudhook URL like a password. Never publish it.
- Home Assistant's internal relay additionally authenticates to Laufapp with the existing strong `health_auto_export_token` via `X-Laufapp-Token`.
- The relay endpoint reuses the hardened HAE parser: authentication before body buffering, JSON-only input, 16 MiB body limit, 120 s body timeout, point/workout limits and idempotent ingestion.
- The Laufapp UI remains Home Assistant Ingress-only on port 8099.
- Do not forward ports 8099 or 8100 on the internet router.

## 1. Secret in Home Assistant

Copy the same strong token configured in the Laufapp app options into Home Assistant's `secrets.yaml`:

```yaml
laufapp_health_auto_export_token: "COPY_THE_EXISTING_LAUFAPP_TOKEN_HERE"
```

Do not commit the real token to GitHub or paste it into automation YAML.

## 2. Internal REST command

Merge `home_assistant/rest_command_laufapp_nabu_casa.yaml.example` into `configuration.yaml`, then validate the Home Assistant configuration and restart Home Assistant.

The target `c87ed7df-laufapp` is the Supervisor-generated DNS hostname for this repository (`ansgarvh/laufapp-homeassistant`) and app slug (`laufapp`). It keeps the request inside the Home Assistant app network.

## 3. Webhook automation

Create a new Home Assistant automation and use the YAML from `home_assistant/automation_laufapp_nabu_casa.yaml.example`.

Replace `REPLACE_WITH_A_NEW_RANDOM_WEBHOOK_ID` with a newly generated random webhook ID. Keep `local_only: true`: Home Assistant permits local-only webhooks from the local network and through Nabu Casa Cloud, while direct internet access to the Home Assistant webhook path stays disabled.

After saving, use Home Assistant Cloud's webhook management to obtain/enable the corresponding `https://hooks.nabu.casa/...` URL. That HTTPS URL is the URL entered in Health Auto Export.

## 4. Health Auto Export settings

Use REST API, JSON, Export Version 2.

For running workouts:

- Data type: Workouts / Running
- Route Data: On
- Workout Metrics: On
- Workout Metrics Time Grouping: Seconds
- Batch requests: On
- Date range: **Previous 7 Days / Letzte 7 Tage**

For recovery/health metrics, use a second automation for resting heart rate, HRV, body mass, VO2max and sleep. `Previous 7 Days` is also recommended there.

Do not add the Laufapp token to Health Auto Export when using the Nabu Casa relay. The public cloudhook secret protects the public endpoint; Home Assistant adds the separate Laufapp token only on the internal relay hop.

## Why Previous 7 Days instead of Since Last Sync?

A generic Home Assistant webhook schedules its automation after receiving the webhook. Its HTTP response to the sender is therefore not an end-to-end acknowledgement that the later REST command and Laufapp ingestion have completed.

Using `Since Last Sync` could advance HAE's checkpoint even if the internal relay later failed. A seven-day overlapping window avoids this single-point delivery risk: recent data is sent again on the next sync, while Laufapp's existing workout/sample/GPS/health-metric deduplication makes repeated delivery idempotent.

The Home Assistant automation is configured as `mode: queued` with a queue of 50 so HAE batch requests are serialized instead of racing each other.

## 5. Disable the temporary LAN port mapping

Only after one real cloudhook test has succeeded, remove the host mapping previously set for `8100/tcp` in the Laufapp network settings and restart the app. It should return to disabled/unpublished. The internal Home Assistant relay will continue to reach container port 8100 by Supervisor DNS.

## Verification

A successful relay should produce an HTTP 200 from the internal REST command and a safe log line beginning with `LAUFAPP_HAE_RELAY_OK`. The normal Laufapp Health Auto Export status should then show the latest synchronization result.

If the internal relay fails, inspect the Home Assistant automation trace and Laufapp logs. Because the HAE automation uses a seven-day overlap, retrying does not create duplicate runs and normally catches the missed data on a later successful execution.

## Test boundary

The repository CI can test the relay endpoint, authentication, idempotency, internal-network Docker path, version consistency and existing regressions. It cannot execute a real Nabu Casa cloudhook or an iPhone HAE background task. Those two integration edges must be verified on the actual Home Assistant OS/iPhone setup after installation.
