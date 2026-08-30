# Laufapp v0.2.8 – Importdiagnose und Prozess-Observability

Datum: 2026-08-30

## Ziel

v0.2.8 behebt keine Trainingslogik, sondern verbessert ausschließlich die Nachvollziehbarkeit großer Apple-Health-Importe und unerwarteter Add-on-Neustarts. Grundlage ist v0.2.7; es gibt keine Datenbankschemamigration.

## Änderungen

- Erfolgreiche `/api/health`- und Gateway-`/health`-Polls werden aus dem Uvicorn-Access-Log gefiltert. Fehlerhafte Health-Requests sowie alle anderen Requests bleiben sichtbar.
- Jeder Apple-Health-Hintergrundjob erhält eine persistente JSONL-Diagnose unter `/data/import_status/<job-uuid>.diagnostics.jsonl`.
- Persistiert werden Queue-/Start-/Fortsetzungs-/Retry-/Abschlussereignisse sowie Phasenwechsel und Fortschritts-Buckets mit den vom Importer gelieferten Detailzählern.
- Bei Fehlern werden Exception-Typ, letzte bekannte Phase, Fortschritt, Detaildaten und vollständiger Python-Traceback dauerhaft gespeichert. Derselbe Traceback wird zusätzlich mit Job-ID und Phase nach stderr geschrieben.
- Unterbrochene Jobs protokollieren beim nächsten Start explizit `resumed_after_restart`.
- Neuer Ingress-geschützter Endpunkt: `GET /api/apple-health/import-jobs/{job_id}/diagnostics?limit=200`.
- `run.sh` protokolliert Prozessstarts, SIGTERM/SIGINT sowie den PID-/Exitstatus des Main- oder optionalen Gateway-Prozesses, bevor das Add-on endet.
- Der Health-Auto-Export-Gateway verwendet den v0.2.8-Entry-Point; sämtliche v0.2.7-Sicherheitsmechanismen bleiben erhalten.

## Daten- und Sicherheitsverträglichkeit

- Keine Änderung am SQLite-Schema.
- Keine Änderung an Apple-Health-Deduplication, Transaktions-/Rollback-Verhalten, detaillierten Samples, GPS-Daten oder Bestzeitenlogik.
- Port 8099 bleibt Home-Assistant-Ingress-only.
- Port 8100 bleibt standardmäßig unveröffentlicht und startet nur mit starkem Sync-Token.
- Die Diagnose-API ist ausschließlich Teil des Ingress-geschützten Hauptprozesses und wird nicht am minimalen Health-Auto-Export-Gateway exponiert.

## Release-Gates

Vor Freigabe müssen erfolgreich sein:

- Python-Compilecheck
- vollständige Pytest-Regression inklusive neuer Diagnose-/Traceback-/Restart-Tests
- JavaScript-Syntaxchecks
- 16-Wochen-Marathonsimulation
- randomisierte Läuferprofile
- pip-audit und Bandit-Gate
- Docker-Build
- Docker-Runtime-E2E inklusive Health Auto Export und hostile Ingress
- Shell-Syntaxprüfung von `run.sh`

Statisch/isoliert und in Linux/Docker getestet; die reale Home-Assistant-/Supervisor-/Nabu-Casa-/VPN-/Health-Auto-Export-iPhone-Integration muss lokal auf dem Beelink verifiziert werden.
