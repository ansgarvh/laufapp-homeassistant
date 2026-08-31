# Laufapp v0.2.14

## Schwerpunkt

Kleine, gezielte Verbesserung der Wochenübersicht auf Basis des vollständig gehärteten v0.2.13-Stands.

### UI
- Absolvierte Einheiten erhalten links in der Wochenkarte einen grünen Haken.
- Der Wochenzeitraum steht direkt oberhalb der sieben Tagesfelder statt in der oberen Wochen-Navigation.
- Vorherige/nächste Woche, „Aktuelle Woche“, Swipe und Drag & Drop bleiben unverändert.

### Kompatibilität und Sicherheit
- Keine Datenbankschemamigration.
- Keine Änderung der Trainingsengine.
- Keine Änderung an Apple Health / Health Auto Export, Nabu-Casa-Relay oder den v0.2.13-Security-Limits.
- Der Service-Worker-Cache wird auf v0.2.14 angehoben, sodass die geänderte Wochenansicht nach dem Update zuverlässig geladen wird.

### Verifikation
Vor Freigabe: vollständige Pytest-Regression, JS-Syntax, Compile, Simulationen, Dependency-/Security-Gates, Docker-Build und HAE-/Ingress-E2E.
