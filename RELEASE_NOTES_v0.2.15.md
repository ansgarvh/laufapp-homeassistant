# Laufapp v0.2.15

## Schwerpunkt

Korrektur der beiden in der realen Home-Assistant-Wochenansicht beobachteten v0.2.14-UI-Regressionsfehler.

### Wochenansicht
- Vorherige Woche, Datumsbereich und nächste Woche bilden wieder eine gemeinsame Navigationszeile direkt oberhalb der Tagesfelder.
- „Aktuelle Woche“ bleibt erhalten, beeinflusst aber nicht die vertikale Position des rechten Pfeils.
- Absolvierte Einheiten zeigen links zuverlässig einen grünen Haken.
- Der Haken basiert direkt auf `workout.status == completed`; kein Text-Scraping und kein MutationObserver sind für diese Funktion mehr aktiv.

### Daten und Kompatibilität
- Bestehender `/api/workouts/{id}/status`-Pfad bleibt unverändert und wird zusätzlich per Roundtrip-Test abgesichert.
- Keine Datenbankschemamigration.
- Keine Änderung an Trainingsplanung, Apple Health/Health Auto Export, Nabu Casa oder Security-Limits.
- Service-Worker-Cache auf v0.2.15 angehoben; `app.js` wird explizit mit v0.2.15 geladen.

### Verifikation
Vollständige Regression, Compile/JS-Syntax, Simulationen, Dependency-/Security-Gates, Docker-Build sowie HAE-/Nabu-/Ingress-E2E sind vor Merge erforderlich.
