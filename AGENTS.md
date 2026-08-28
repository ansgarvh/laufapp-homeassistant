# Mandatory repository instructions

These rules apply to every change in this repository.

## Work conservatively

- Inspect the existing implementation, affected callers, tests, and compatibility/safety paths before editing.
- Prefer the smallest change that solves the task. Do not combine fixes with unrelated refactors or remove working safeguards for style.
- Treat regressions as unacceptable. Never commit personal running/Health data, production databases, exports, secrets, API keys, credentials, or private screenshots.

## Preserve data and architecture

- User data lives persistently in `/data/laufapp.sqlite3` and must survive normal Home Assistant App updates. Never silently recreate a database after an error.
- Database changes require an explicit versioned migration: detect the schema, reject unsupported downgrades, create and integrity-check a pre-migration backup, migrate additively, update markers, integrity-check the result, and restore/fail startup on error. Avoid destructive SQL.
- Preserve persistent Apple Health background jobs, retry/resume and deduplication behavior, transactional imports, the 24-month filter, and detailed `run_samples`/`gps_points` data.
- Preserve the explicit accept/reject gate for AI plan changes and keep the OpenAI API key server-side.

## Home Assistant security

- Normal access is authenticated Home Assistant Ingress. Keep `ingress: true`, port 8099 unpublished by default, and `ingress_stream: true`.
- Preserve the production ingress-only middleware: trusted `X-Hass-Source: core.ingress` plus a valid `X-Ingress-Path`, blocked direct remote requests, and localhost health checks. Do not replace this with apparent client-IP trust.

## Testing and releases

- Run targeted tests and the complete pytest suite. Before a release also run Python compile checks, JavaScript syntax checks, Home Assistant config/version checks, Docker build where available, relevant security/migration/import tests, and static/mobile checks for affected UI.
- Perform the most complete realistic synthetic end-to-end workflow available before every meaningful release, including artifact/database validation and relevant error/restart paths.
- Never describe a mock, static check, or isolated test as a real Home Assistant, Supervisor, Nabu Casa, Beelink, OpenAI, or production test. State unavailable platform validation explicitly.
- Do not release with failing tests. Keep `laufapp/config.yaml`, the application version, Docker metadata/defaults, cache version, changelog, and relevant documentation consistent.
- Commit changes and open a pull request for review; do not merge or publish a release unless explicitly requested.
