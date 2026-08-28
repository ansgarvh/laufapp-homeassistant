# Laufapp project context

## Purpose and product boundary

Laufapp is a private, single-user running coach for preparation toward 5 km, 10 km, half-marathon, and marathon goals. It combines race targets, local training history, Apple Health recovery/performance data, deterministic planning and prediction, and an optional AI coach. It is not a multi-user service. Health and running data remain local by default, and the product favors conservative, explainable adjustments over aggressive automation.

## Deployment architecture

The production target is an amd64 Beelink Mini S12 running Home Assistant OS. Laufapp is a Home Assistant custom App: a Python 3.13 container runs Uvicorn/FastAPI on internal port 8099 and serves both a JSON API and a mobile-first PWA. Normal UI access is through authenticated Home Assistant Ingress. `ports.8099/tcp` is null, so the application is not normally published directly to the LAN or Internet. `/data` is the persistent App volume; `/share` is mapped read/write only for the controlled legacy-local-App to repository-App transfer.

GitHub is the canonical code source. `laufapp/config.yaml` is the Home Assistant App manifest and its version drives update discovery. The Dockerfile installs `laufapp/requirements.txt`, copies `laufapp/app/`, and starts `run.sh`; its health check calls `/api/health` on localhost.

## Repository structure

- `laufapp/config.yaml`, `Dockerfile`, `run.sh`, and `requirements.txt`: Home Assistant/container packaging.
- `laufapp/app/main.py`: FastAPI lifecycle, ingress guard, request models, APIs, and static-file routes.
- `laufapp/app/db.py`: persistent paths, schema 2, defaults, migrations/backups, and repository transfer.
- `laufapp/app/health_import.py`: streaming Apple Health XML/ZIP parsing, filtering, deduplication, sample association, and GPX ingestion.
- `laufapp/app/import_jobs.py`: persisted Health job creation, status/progress, worker execution, retry, and restart recovery.
- `laufapp/app/training.py`: week generation, run matching, guardrails, predictions, and dashboard summaries.
- `laufapp/app/coach.py`: server-side OpenAI configuration, budget tracking, coach context, evidence tools, and suggestion validation.
- `laufapp/app/static/`: HTML, CSS, JavaScript, manifest, service worker, and PWA icons.
- `tests/`: API, migration, ingress, import, detail-metric, mocked-AI, static-release, and synthetic end-to-end regression tests.
- `.github/workflows/ci.yml`: Python 3.13 compile/test, Node syntax, and Docker build checks.

Some documentation is duplicated at the repository root and below `laufapp/` because Home Assistant displays files from the App directory; release-relevant copies should stay aligned.

## Implemented product surfaces

The frontend bottom navigation contains **Heute**, **Woche**, **Fortschritt**, **Coach**, and **Mehr**. Implemented APIs and UI cover race setup/targets, dashboard and recovery summaries, four-session weekly plans, moving and status changes, performance marks and predictions, manual/imported runs, shoe assignment/archive and mileage, Health imports/job status, AI chat/review/suggestions, preferences, and repository transfer.

The app is mobile-first with a 940 px maximum shell, fixed bottom navigation, compact cards, and explicit 320 px minimum layout support. Detailed run data is currently exposed by an API summary endpoint, but comprehensive analysis charts for those time series/routes are not yet implemented.

## Persistent storage and migration architecture

Production data is `/data/laufapp.sqlite3`. SQLite uses foreign keys, WAL, and a busy timeout. Schema 2 contains settings, races, shoes, runs, health metrics, workouts, performance marks, prediction history, AI suggestions/chat/usage/reviews, import jobs, run samples, GPS points, and migration logs.

Databases from v0.1.0–v0.1.2 have an implicit legacy schema and are treated as schema 1. Startup detects the schema, blocks a newer-schema downgrade, creates an online SQLite backup under `/data/backups`, verifies it, applies the additive 1→2 migration transactionally, writes `PRAGMA user_version` and settings markers, and runs a final integrity check. On migration failure, the database is restored from the backup and startup fails. A same-schema startup repairs only through idempotent `CREATE IF NOT EXISTS` statements and updates application metadata.

The one-time local-App→GitHub-App bridge writes an integrity-checked snapshot to `/share/laufapp-transfer/`. A fresh repository App may adopt it; an existing destination database is never overwritten.

## Apple Health import architecture

The preferred historical path uploads a native XML or ZIP into `/data/imports` and immediately returns a persistent job identifier. A daemon worker processes it server-side, persists phase/progress/result/error state, and removes the upload after success. Processing jobs left by a restart are queued again; failed jobs can be retried while the source exists. Inserts are deduplicated and the Health data operation is transactional, limiting partial-import risk. The UI polls phases after upload, so the browser must remain open only until transfer completion.

The parser limits records to the last 24 calendar months and reads `export.xml` incrementally with `iterparse`; ZIP member paths and expanded size are guarded. The HTTP upload guard is approximately 2 GB. Resting heart rate, HRV, weight, VO₂max, sleep intervals, and running workouts are supported.

For runs, the importer stores summary fields plus time-resolved heart rate, speed, power, stride length, vertical oscillation, ground-contact time, and cadence derived from step-count samples. Samples are staged then associated by workout interval. GPX routes are matched by timestamp and stored as ordered latitude/longitude/elevation points; ascent may be derived from elevations. Availability depends on what Apple includes in the export.

## Training and prediction principles

Exactly four configurable training weekdays are stored by default. The local engine builds easy, quality, long, race-specific, taper, and race sessions from the active race, preferences, performance anchors, recent volume, and phase. It avoids overwriting non-planned workouts unless explicitly forced and retains origin-week information when sessions move. Guardrails report hard-session spacing, weekly-volume jumps, and long-run share/limits. These rules are useful but are not a clinically validated individualized training prescription.

Race predictions use available performance marks and suitable runs, a Riegel-style conversion, recency/consistency/endurance adjustments, and deterministic confidence/ranges for the four standard distances. This is more transparent than a single exact value, but remains a heuristic rather than a mature personalized physiological model.

## AI Coach behavior

The optional coach reads its API key from `/data/options.json` or the server environment and returns configuration status without exposing the key. Usage and estimated monthly cost are stored locally, with a default €10 budget guard. The coach can interpret context, analyze runs/screenshots, and create evidence-assisted week reviews. A suggestion is validated and persisted as pending; a workout changes only through the separate explicit accept endpoint, while reject resolves it without mutation.

The model identifiers presently stored as defaults are implementation strings and have not been validated by this v0.1.4 task against current OpenAI production availability/pricing. Real API configuration and calls remain production work.

## Security architecture

With `LAUFAPP_TRUSTED_INGRESS_ONLY=1` (the image default), middleware permits localhost container traffic or requests containing both `X-Hass-Source: core.ingress` and an `X-Ingress-Path` beginning `/api/hassio_ingress/`; other direct requests receive 403. This deliberately does not trust the proxy-rewritten apparent client IP. Home Assistant config enables Ingress and streaming while leaving direct port publication disabled. The API key is server-only, uploaded screenshots are not persisted, and Health data should not be logged or sent externally wholesale.

## Release workflow and validation boundary

The intended flow is request/issue → implementation branch → local checks → pull request → GitHub Actions → review → merge to `main` → Home Assistant update discovery. Releases require consistent version markers, changelog/docs updates, a full regression suite, targeted tests, compile and JavaScript checks, config/Docker validation, and the most complete available synthetic E2E workflow. Schema changes additionally require migration documentation and preservation tests. Pull requests are not auto-merged.

Static/unit/synthetic checks are not evidence of real Home Assistant behavior. Actual Supervisor installation/update, Nabu Casa proxying, large-upload streaming, persistent `/data` behavior across a real App update, amd64 image execution, and performance on the Beelink must be reported as production validation only when run there.

## Known constraints and future work

- v0.1.4 enables Home Assistant Ingress streaming to address observed large uploads stalling around 35%; the fix still needs a real large-export test through Home Assistant/Nabu Casa on the Beelink.
- Continuous synchronization is not implemented. The preferred future direction is direct REST/JSON ingestion from Health Auto Export or an equivalent iOS exporter, not thousands of Home Assistant entities.
- Detailed metrics/routes are stored but need dedicated run-analysis views.
- Prediction quality should improve only after sufficient local history supports runner-specific calibration.
- Production AI model/API/pricing configuration and evidence behavior require official-document verification and real opt-in testing.
- Interrupted jobs restart from queued processing and rely on deduplication; byte-level parser checkpointing is not implemented.
- The synchronous `/api/apple-health/import` endpoint remains for compatibility/tests; the persistent job endpoint is the production architecture.
- Continued UI polish and real-device 320/390 px checks remain ongoing, especially whenever screens change.
