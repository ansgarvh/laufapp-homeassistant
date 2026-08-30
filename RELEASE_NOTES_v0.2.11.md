# Laufapp v0.2.11 – Large Health Auto Export Webhook Relay

Release date: 2026-08-30

## Problem fixed

The v0.2.10 Home Assistant automation forwarded webhook JSON with `{{ trigger.json | to_json }}` into a `rest_command`. Detailed Health Auto Export workouts with second-level metrics exceeded Home Assistant's 262144-character template-output ceiling and failed before the internal Laufapp relay was called. In the real target installation, the dedicated `hooks.nabu.casa` cloudhook also returned HTTP 413 for the large HAE request, while the normal Nabu Casa Remote UI webhook path successfully reached Home Assistant.

## New architecture

v0.2.11 adds `custom_components/laufapp_hae_relay`, a small YAML-configured Home Assistant custom integration. It registers a POST-only webhook and forwards the incoming raw JSON body directly to the already hardened Laufapp endpoint:

```text
Health Auto Export
  -> HTTPS
https://<remote-id>.ui.nabu.casa/api/webhook/<secret-id>
  -> Home Assistant webhook API
laufapp_hae_relay custom integration
  -> Supervisor-internal HTTP
http://c87ed7df-laufapp:8100/home-assistant-relay
  -> X-Laufapp-Token
Laufapp HAE importer
```

No Jinja template or Home Assistant automation is used in the production HAE data path.

## Security

- Port 8099 remains Home Assistant Ingress-only.
- Port 8100 remains unpublished and is reached only through Supervisor-internal DNS.
- The public webhook ID and internal Laufapp token remain separate secrets.
- The public HAE request does not contain the Laufapp token.
- The custom relay accepts POST only, requires `application/json`, and enforces a 16 MiB request limit.
- The internal destination is fixed to the Laufapp relay endpoint and cannot be configured as an arbitrary proxy target.
- The existing Laufapp gateway still performs its own strong-token authentication, request-size/timeout checks, payload validation, workout/point limits and idempotent import handling.
- Request bodies, tokens and webhook IDs are not logged by the custom relay.

## Compatibility

There is no database migration and no change to training planning, predictions, best times, Apple Health historical import, detailed workout storage, GPS handling or Home Assistant Ingress behavior. The direct `/health-auto-export` endpoint and the v0.2.10 internal `/home-assistant-relay` endpoint remain compatible.

The old webhook-automation/rest-command example remains in the repository only as a legacy small-payload diagnostic. It is no longer recommended for detailed HAE workout synchronization.

## Installation note

The Home Assistant custom integration must be copied to:

```text
/config/custom_components/laufapp_hae_relay/
```

and configured in `configuration.yaml` with a secret webhook ID and the existing Laufapp Health Auto Export token. Full instructions are in `NABU_CASA_HEALTH_SYNC.md`.

## Test scope

Release gates include Python compile checks, JavaScript syntax checks, the full regression suite, an isolated relay test with a body larger than 262144 bytes, relay request limits and fail-closed validation, 16-week marathon simulation, randomized runner simulations, dependency/security scans, Docker build, direct HAE import, internal relay idempotence, gateway fail-closed behavior and Home Assistant Ingress network-security simulations.

Statisch/isoliert und in Linux/Docker getestet; die reale Home-Assistant-OS-/Custom-Integration-/Nabu-Casa-Remote-UI-/Health-Auto-Export-iPhone-Integration muss lokal auf dem Zielsystem verifiziert werden.
