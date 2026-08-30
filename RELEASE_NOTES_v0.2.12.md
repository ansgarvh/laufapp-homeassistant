# Laufapp v0.2.12

## Zweck

v0.2.12 behebt die mit realen Health-Auto-Export-JSON-v2-Daten nachgewiesene Ursache dafür, dass neue Läufe trotz erfolgreicher Übertragung nicht in der Laufapp angelegt wurden.

Health Auto Export liefert deutsche Apple-Laufworkouts in den untersuchten realen Exporten als `Outdoor Ausführen`. Der bisherige v0.2.11-Importpfad akzeptierte nur Workout-Namen mit `run` oder `lauf` und verwarf diese Datensätze daher vor dem eigentlichen Import.

## Änderungen

- Lokalisierte HAE-Laufnamen wie `Outdoor Ausführen` und `Indoor Ausführen` werden erkannt; bestehende Running-/Run-/Lauf-/Laufen-Namen bleiben kompatibel.
- Der Fix liegt als additive Kompatibilitätsschicht vor dem bestehenden gehärteten v0.2.7-Importer. Authentifizierung, Body-Limits, Workout-ID-Kollisionsschutz, Cross-Source-Deduplizierung, SQLite-Insertlogik und Performance-Mark-Sync bleiben erhalten.
- Ein vorhandenes `activeEnergyBurned` bleibt die bevorzugte Quelle für aktive Kalorien.
- Fehlt `activeEnergyBurned`, wird eine vollständig valide `activeEnergy[]`-Zeitreihe sicher nach kcal aggregiert. Bei unbekannten oder gemischten Einheiten wird kein Teilwert erfunden.
- `totalEnergy` wird nicht als Ersatz für aktive Energie verwendet, da es in realen HAE-Daten zusätzlich Basalenergie enthalten kann.
- Die offizielle HAE-Workout-Distanz bleibt autoritativ. GPS-Koordinaten werden nicht zur Ersetzung der Workout-Distanz aufsummiert.
- Rohe GPS-Höhenwerte werden nicht naiv zu Höhenmetern aufsummiert; bei fehlendem belastbarem Summenfeld bleibt der Höhenmeterwert leer statt stark überhöht zu werden.
- Ist in HAE das Einschließen der Route aktiviert, wird die Route aus dem JSON-`route`-Array verarbeitet. Die parallel exportierte GPX-Datei ist für den REST-Import nicht zusätzlich erforderlich.

## Reale Regressionen

Die neuen Regressionstests bilden zwei beobachtete HAE-Feldformen nach:

1. Langer Lauf vom 30.08.2026: 34,020402 km, 10.093,704 s, lokalisierter Name `Outdoor Ausführen`, Herzfrequenz-/Kadenzdaten, GPS-Route und `activeEnergy[]`, jedoch ohne `activeEnergyBurned`.
2. Kurzer Lauf vom 27.08.2026: 0,932501 km, 289,071 s, lokalisierter Name `Outdoor Ausführen`, Herzfrequenz-/Kadenzdaten, GPS-Route sowie explizites `activeEnergyBurned` zusätzlich zur Energiezeitreihe.

Zusätzlich wird geprüft, dass Nicht-Lauf-Workouts weiterhin nicht importiert werden und Reimports idempotent bleiben.

## Kompatibilität und Sicherheit

- Keine Datenbankschemamigration.
- Keine Änderung an Trainingsplanung, Prognosen, Bestzeitenlogik oder historischem Apple-Health-ZIP/XML-Import.
- Home-Assistant-Ingress bleibt unveröffentlicht und geschützt.
- Der v0.2.11-Raw-JSON-Relay für große HAE-Payloads bleibt unverändert.
- Port 8100 bleibt unveröffentlicht und tokenpflichtig.
- Bestehende Benutzerdaten bleiben erhalten.

## Verifikation

Release-Gates: Python-Compilecheck, JavaScript-Syntaxcheck, vollständige Pytest-Regression, reale HAE-Shape-Regressionen, Marathon-/Random-Simulationen, Dependency-Audit, Security-Gate, Docker-Build und Docker-E2E für direkten HAE-Import, Nabu-Casa-Relay sowie Home-Assistant-Ingress.

Statisch/isoliert getestet; die Home-Assistant-OS-/Nabu-Casa-/Health-Auto-Export-iPhone-Integration muss nach Installation auf dem Zielsystem zusätzlich real verifiziert werden.
