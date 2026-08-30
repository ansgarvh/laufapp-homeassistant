# Laufapp v0.2.11

Private, mobile-first Lauf-PWA für Home Assistant OS. Laufapp verbindet eine lokale Trainings-/Prognoseengine mit Apple-Health-Daten, Health Auto Export und einem optionalen OpenAI-Coach. Die Anwendung ist für einen einzelnen privaten Nutzer ausgelegt.

## Neu in v0.2.11 – große Health-Auto-Export-Payloads ohne Template-Limit

v0.2.11 ersetzt für detaillierte HAE-Workouts den v0.2.10-Automations-/`rest_command`-Relay durch eine kleine Home-Assistant-Custom-Integration:

`iPhone / HAE → HTTPS → <remote-id>.ui.nabu.casa/api/webhook/<secret-id> → Home Assistant Custom Integration → internes App-Netz → Laufapp`

Wesentliche Änderungen:

- **Kein Jinja-Serialisieren großer HAE-Payloads mehr:** Der neue Handler liest den Webhook-Body direkt. Damit umgeht er die reale Home-Assistant-Fehlermeldung `Template output exceeded maximum size of 262144 characters`, die bei sekündlichen Workout-Metriken auftrat.
- **Nabu Casa Remote UI statt dediziertem Cloudhook:** In der realen Zielinstallation erreichte ein kleiner Request den Cloudhook, während der große HAE-Request dort HTTP 413 erhielt. Der bereits erfolgreich getestete `.ui.nabu.casa/api/webhook/...`-Pfad wird deshalb direkt verwendet.
- **Separate Custom Integration:** `custom_components/laufapp_hae_relay` registriert einen POST-only-Webhook, akzeptiert ausschließlich JSON, begrenzt den Body auf 16 MiB und leitet die Bytes ohne Jinja/Automation an `http://c87ed7df-laufapp:8100/home-assistant-relay` weiter.
- **Zwei getrennte Geheimnisse:** Die öffentliche Webhook-ID bleibt geheim; der starke Laufapp-Token wird ausschließlich auf dem internen Home-Assistant→Laufapp-Hop als `X-Laufapp-Token` ergänzt.
- **Port 8100 bleibt unveröffentlicht:** Die Custom Integration nutzt den Supervisor-internen DNS-Namen. Eine Host-/Router-Portfreigabe ist nicht erforderlich.
- **Legacy-Pfad bleibt dokumentiert, aber nicht für echte Workout-Payloads empfohlen:** Die v0.2.10-Webhook-Automation und der `rest_command` bleiben als kleine Diagnose-/Kompatibilitätsbeispiele im Repository, sind jedoch wegen des 262144-Zeichen-Template-Limits nicht der Produktionspfad für detaillierte HAE-Daten.
- **Keine Datenbankschemamigration und keine Änderung an Trainingslogik, Prognosen, Ingress, Apple-Health-Historienimport oder HAE-Importer.**

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

Empfohlene Lauf-Automation bei Nutzung des v0.2.11-Relays:

- Automation: REST API
- Ziel-URL: `https://<remote-id>.ui.nabu.casa/api/webhook/<secret-webhook-id>`
- Format: JSON, Export Version 2
- Zeitraum: **Previous 7 Days / Letzte 7 Tage**
- Daten: Workouts → Running
- Route Data: On
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

Benutzerdaten liegen im persistenten Home-Assistant-`/data`-Bereich. v0.2.11 benötigt **keine Datenbankschemamigration**; bestehende Läufe, Health-Daten, Bestzeiten, Schuhe, Rennen, Trainingsplan, Einstellungen und Coach-Daten bleiben erhalten.

## OpenAI

Der OpenAI-API-Key bleibt serverseitig in der Home-Assistant-App-Konfiguration und wird nicht an das Browser-Frontend ausgeliefert. Laufapp funktioniert für Plan, Prognosen, Health-Import, Wochenübersicht, Läufe, Schuhe und Rennen vollständig ohne OpenAI-Key.

## Release-Prüfungen

Vor Merge laufen Python-Compilecheck einschließlich Custom Integration, JavaScript-Syntaxcheck, vollständige Pytest-Regression über den v0.2.11-Entry-Point, ein isolierter >262144-Zeichen-Relaytest, 16-Wochen-Marathonsimulation, neun randomisierte Läuferprofile, `pip-audit`, Bandit-Gate, Docker-Build, direkter Health-Auto-Export-E2E, interner Relay-E2E über ein separates Docker-Netz, externe Ingress-Spoofing-Negativtests sowie die positive Home-Assistant-Ingress-Netzsimulation.

Statisch/isoliert und in Linux/Docker getestet. Die echte Home-Assistant-OS-/Custom-Integration-/Nabu-Casa-Remote-UI-/Health-Auto-Export-iPhone-Integration muss nach Installation auf dem Zielsystem lokal verifiziert werden.

## Lokale Entwicklung

```bash
cd laufapp/app
export LAUFAPP_DATA_DIR=/tmp/laufapp-data
export LAUFAPP_TRANSFER_DIR=/tmp/laufapp-transfer
export LAUFAPP_TRUSTED_INGRESS_ONLY=0
export LAUFAPP_HEALTH_AUTO_EXPORT_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
uvicorn main_v0211:app --host 127.0.0.1 --port 8099 --no-proxy-headers
```

Weitere Details: `SECURITY.md`, `NABU_CASA_HEALTH_SYNC.md`, `RELEASE_NOTES_v0.2.11.md`, `TRAINING_ENGINE.md`, `MIGRATIONS.md`.