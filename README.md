# Laufapp v0.2.12

Private, mobile-first Lauf-PWA für Home Assistant OS. Laufapp verbindet eine lokale Trainings-/Prognoseengine mit Apple-Health-Daten, Health Auto Export und einem optionalen OpenAI-Coach. Die Anwendung ist für einen einzelnen privaten Nutzer ausgelegt.

## Neu in v0.2.12 – reale deutsche Health-Auto-Export-Läufe

v0.2.12 behebt einen mit echten HAE-JSON-v2-Exporten nachgewiesenen Kompatibilitätsfehler: Deutsche Apple-Laufworkouts kommen in Health Auto Export als `Outdoor Ausführen` an. Der bisherige Parser akzeptierte nur Workout-Namen mit `run` oder `lauf` und verwarf diese Läufe daher, bevor Distanz, Herzfrequenz oder GPS verarbeitet wurden.

Wesentliche Änderungen:

- **Lokalisierte Laufnamen:** `Outdoor Ausführen` und `Indoor Ausführen` werden als Laufworkouts erkannt; bestehende englische und deutsche Running-/Lauf-Bezeichnungen bleiben kompatibel.
- **Reale HAE-Feldformen getestet:** Regressionstests basieren auf den beobachteten Strukturen eines 34,020-km-Laufs und eines 0,933-km-Laufs. Workout-ID, offizielle Distanz, Dauer, Herzfrequenz, Kadenz und GPS-Route bleiben unverändert und werden weiterhin vom bestehenden gehärteten Importer gespeichert.
- **Aktive Energie robust:** Ein vorhandenes `activeEnergyBurned`-Summenfeld bleibt maßgeblich. Fehlt es, kann v0.2.12 eine vollständig valide `activeEnergy[]`-Zeitreihe in kcal aggregieren. `totalEnergy` wird dabei nicht als aktive Energie missinterpretiert, weil es auch Grundumsatzenergie enthalten kann.
- **Offizielle Distanz bleibt autoritativ:** GPS-Punkte dienen Route/Höhenprofil und ersetzen nicht die HAE-Workout-Distanz. Rohe GPS-Höhenwerte werden nicht naiv zu Höhenmetern aufsummiert.
- **Route Data erforderlich:** Ist die HAE-Option zum Einschließen der Route aktiviert, liegt die GPS-Route bereits im JSON unter `route`; eine separate GPX-Datei muss serverseitig nicht zusätzlich verarbeitet werden.
- **Keine Datenbankschemamigration:** Trainingslogik, Prognosen, Bestzeiten, historischer Apple-Health-Import, Deduplizierung, Home-Assistant-Ingress und der v0.2.11-Nabu-Casa-Relay bleiben unverändert.

Der v0.2.11-Transport für große HAE-Payloads bleibt bestehen:

`iPhone / HAE → HTTPS → <remote-id>.ui.nabu.casa/api/webhook/<secret-id> → Home Assistant Custom Integration → internes App-Netz → Laufapp`

Die vollständige Einrichtung steht in `NABU_CASA_HEALTH_SYNC.md`. Die Home-Assistant-Konfigurationsbeispiele liegen unter `home_assistant/`.

## Importdiagnose aus v0.2.8 / Ingress-Fix aus v0.2.9

- Erfolgreiche `/api/health`- und Gateway-`/health`-Polls werden aus dem Uvicorn-Access-Log gefiltert; fehlerhafte Health-Requests und alle anderen API-Aufrufe bleiben sichtbar.
- Phasenwechsel und Fortschritt jedes Apple-Health-Imports werden als JSONL unter `/data/import_status/<job-uuid>.diagnostics.jsonl` gespeichert.
- Background-Job-Fehler speichern Exception-Typ, letzte Phase, Fortschritt, Detaildaten und vollständigen Python-Traceback.
- `run.sh` protokolliert SIGTERM/SIGINT sowie den PID-/Exitstatus von Main- und Gateway-Prozess.
- Diagnose-API: `GET /api/apple-health/import-jobs/{job_id}/diagnostics`.
- Port 8099 bleibt Home-Assistant-Ingress-only. Der dokumentierte Proxy `172.30.32.2` sowie der eng begrenzte authentifizierte Kompatibilitätspfad innerhalb `172.30.32.0/23` bleiben unverändert erhalten.

## Security-Basis

- Port **8099** bleibt Home-Assistant-Ingress-only und ist in `config.yaml` nicht als Host-Port veröffentlicht.
- Port **8100** bleibt standardmäßig unveröffentlicht und startet nur mit einem starken Health-Auto-Export-Token. Für den Home-Assistant-Relay muss er nicht am Host veröffentlicht werden.
- Uvicorn läuft ohne Proxy-Header-Vertrauen.
- Health Auto Export authentifiziert vor dem Body-Lesen, ist JSON-only, besitzt Größen-/Timeout-/Mengenlimits und gibt keine persönlichen Read-Daten zurück.
- Öffentliche Webhook-ID und Laufapp-Token sind zwei getrennte Geheimnisse: Die Webhook-ID schützt den öffentlichen HTTPS-Eingang, der Laufapp-Token ausschließlich den internen Home-Assistant→Laufapp-Hop.
- Die Custom Integration besitzt ein fest verdrahtetes internes Ziel und kann daher nicht als beliebiger HTTP-Proxy missbraucht werden.
- Der klassische Apple-Health-ZIP/XML-Pfad behält ZIP-Bomb-Limits, GPX-Grenzen und `defusedxml`-Schutz.
- Security-CI umfasst `pip-audit`, Bandit-Gate, externe Spoofing-Negativtests, positive Home-Assistant-Ingress-Simulation sowie den internen HAE-Relay-Pfad inklusive Authentifizierung und idempotentem Reimport.

Ausführliche Details und verbleibende Risiken stehen in `SECURITY.md` und `NABU_CASA_HEALTH_SYNC.md`.

## Health Auto Export

Laufapp verarbeitet Health Auto Export per REST API, JSON Export Version 2. Unterstützt werden Laufworkout, Start/Ende, Dauer, Distanz, Kalorien, Höhenmeter, mittlere und zeitaufgelöste Herzfrequenz, Running Speed, Running Power, Schrittlänge, vertikale Oszillation, Bodenkontaktzeit, Kadenz, GPS-Route/Höhe sowie Ruhepuls, HRV/SDNN, Gewicht, VO₂max und Schlafdauer.

Empfohlene Lauf-Automation bei Nutzung des v0.2.12-Relays:

- Automation: REST API
- Ziel-URL: `https://<remote-id>.ui.nabu.casa/api/webhook/<secret-webhook-id>`
- Format: JSON, Export Version 2
- Zeitraum: **Previous 7 Days / Letzte 7 Tage**
- Daten: Workouts → Running
- Route Data / GPX-Routen einschließen: **On**
- Workout Metrics: On
- Workout Metrics Time Grouping: Seconds
- Batch Requests: On
- Kein Laufapp-Token im iPhone-Request; Home Assistant ergänzt ihn erst intern.

Für Ruhepuls, HRV, Gewicht, VO₂max und Schlaf empfiehlt sich eine zweite, weniger häufige Health-Metrics-Automation, ebenfalls mit überlappendem 7-Tage-Fenster.

Der bestehende direkte Gateway-Pfad `POST /health-auto-export` bleibt aus Kompatibilitätsgründen erhalten. Er darf nur über einen anderweitig verschlüsselten privaten Transport verwendet werden; für das hier eingesetzte Nabu-Casa-Setup wird er nicht öffentlich exponiert.

## Bestehende Funktionen

- Heute: Planfokus, Zielzeit, Prognose, nächste Einheit, Recovery-Signale und Coach-Vorschläge
- Wochenübersicht: 3–7 konfigurierbare Lauftage, Verschieben/Tauschen, Status, Wochenkilometer und Planbegründungen
- Rennen: mehrere A-/B-Rennen mit eigener Zielzeit
- Trainingssteuerung: wissenschaftlich orientierte Periodisierung, Workout-Variation, Deload/Taper, Longrun-/Qualitätsbudget und Planungsaggressivität
- Fortschritt: Prognosen für 5 km, 10 km, Halbmarathon und Marathon sowie sichtbare Bestzeiten
- Apple Health: manueller ZIP/XML-Import der letzten 24 Monate als Historien-/Fallbackpfad
- detaillierte Laufdaten: HR, Speed, Power, Schrittlänge, vertikale Oszillation, Bodenkontaktzeit, Kadenz, GPS/Höhe soweit vorhanden
- Schuhe: Stammdaten und Kilometerbilanz
- AI Coach: optionaler Chat, Screenshot-Auswertung und ausschließlich bestätigungspflichtige Planänderungen

## Persistenz

Benutzerdaten liegen im persistenten Home-Assistant-`/data`-Bereich. v0.2.12 benötigt **keine Datenbankschemamigration**; bestehende Läufe, Health-Daten, Bestzeiten, Schuhe, Rennen, Trainingsplan, Einstellungen und Coach-Daten bleiben erhalten.

## OpenAI

Der OpenAI-API-Key bleibt serverseitig in der Home-Assistant-App-Konfiguration und wird nicht an das Browser-Frontend ausgeliefert. Laufapp funktioniert für Plan, Prognosen, Health-Import, Wochenübersicht, Läufe, Schuhe und Rennen vollständig ohne OpenAI-Key.

## Release-Prüfungen

Vor Merge laufen Python-Compilecheck einschließlich Custom Integration, JavaScript-Syntaxcheck, vollständige Pytest-Regression über den v0.2.12-Entry-Point, die realitätsnahen HAE-v2-Regressionstests, ein isolierter >262144-Zeichen-Relaytest, 16-Wochen-Marathonsimulation, neun randomisierte Läuferprofile, `pip-audit`, Bandit-Gate, Docker-Build, direkter Health-Auto-Export-E2E, interner Relay-E2E über ein separates Docker-Netz, externe Ingress-Spoofing-Negativtests sowie die positive Home-Assistant-Ingress-Netzsimulation.

Statisch/isoliert und in Linux/Docker getestet. Die echte Home-Assistant-OS-/Custom-Integration-/Nabu-Casa-Remote-UI-/Health-Auto-Export-iPhone-Integration muss nach Installation auf dem Zielsystem lokal verifiziert werden.

## Lokale Entwicklung

```bash
cd laufapp/app
export LAUFAPP_DATA_DIR=/tmp/laufapp-data
export LAUFAPP_TRANSFER_DIR=/tmp/laufapp-transfer
export LAUFAPP_TRUSTED_INGRESS_ONLY=0
export LAUFAPP_HEALTH_AUTO_EXPORT_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
uvicorn main_v0212:app --host 127.0.0.1 --port 8099 --no-proxy-headers
```

Weitere Details: `SECURITY.md`, `NABU_CASA_HEALTH_SYNC.md`, `RELEASE_NOTES_v0.2.12.md`, `TRAINING_ENGINE.md`, `MIGRATIONS.md`.