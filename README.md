# Laufapp v0.2.9

Private, mobile-first Lauf-PWA für Home Assistant OS. Laufapp verbindet eine lokale Trainings-/Prognoseengine mit Apple-Health-Daten, Health Auto Export und einem optionalen OpenAI-Coach. Die Anwendung ist für einen einzelnen privaten Nutzer ausgelegt.

## Neu in v0.2.9 – Home-Assistant-Ingress-Kompatibilität

v0.2.9 korrigiert die in v0.2.7 zu streng gewordene Ingress-Vertrauensgrenze, ohne den Port 8099 nach außen zu öffnen oder den Header-Spoofing-Schutz zurückzunehmen.

Wesentliche Änderungen:

- **Dokumentierter Standard bleibt erhalten:** Verbindungen vom Home-Assistant-Ingress-Proxy `172.30.32.2` werden weiterhin akzeptiert.
- **Sicherer Kompatibilitätspfad:** Ein anderer Peer wird nur akzeptiert, wenn seine TCP-Adresse im internen Home-Assistant-Netz `172.30.32.0/23` liegt und gleichzeitig ein gültig aussehender `X-Ingress-Path` plus ein authentifizierter Benutzer-/Ingress-Marker vorhanden ist.
- **Externe Spoofing-Versuche bleiben gesperrt:** Ein externer Client kann auch mit gefälschtem `X-Forwarded-For`, `X-Hass-Source`, `X-Ingress-Path` und `X-Remote-User-Id` den Zugriff nicht freischalten.
- **Blockierte Zugriffe werden diagnostizierbar:** Der Server protokolliert Peer-IP, Pfad und nur das Vorhandensein relevanter Ingress-Marker über `LAUFAPP_INGRESS_BLOCKED`, ohne Benutzer-IDs auszugeben.
- **Neue positive Docker-E2E-Prüfung:** Die CI erzeugt ein eigenes `172.30.32.0/23`-Netz und prüft sowohl den dokumentierten `.2`-Proxy als auch den abgesicherten internen Fallback sowie den negativen Fall ohne Authentifizierungsmarker.
- **Keine Datenbankschemamigration und keine Änderung an Trainingslogik, Apple-Health-Daten, Prognosen oder Health Auto Export.**

## Importdiagnose aus v0.2.8

- Erfolgreiche `/api/health`- und Gateway-`/health`-Polls werden aus dem Uvicorn-Access-Log gefiltert; fehlerhafte Health-Requests und alle anderen API-Aufrufe bleiben sichtbar.
- Phasenwechsel und Fortschritt jedes Apple-Health-Imports werden als JSONL unter `/data/import_status/<job-uuid>.diagnostics.jsonl` gespeichert.
- Background-Job-Fehler speichern Exception-Typ, letzte Phase, Fortschritt, Detaildaten und vollständigen Python-Traceback.
- `run.sh` protokolliert SIGTERM/SIGINT sowie den PID-/Exitstatus von Main- und Gateway-Prozess.
- Diagnose-API: `GET /api/apple-health/import-jobs/{job_id}/diagnostics`.

## Security-Basis

- Port **8099** bleibt Home-Assistant-Ingress-only und ist in `config.yaml` nicht als Host-Port veröffentlicht.
- Port **8100** bleibt standardmäßig unveröffentlicht und startet nur mit einem starken Health-Auto-Export-Token.
- Uvicorn läuft ohne Proxy-Header-Vertrauen.
- Health Auto Export authentifiziert vor dem Body-Lesen, ist JSON-only, besitzt Größen-/Timeout-/Mengenlimits und gibt keine persönlichen Read-Daten zurück.
- Der klassische Apple-Health-ZIP/XML-Pfad behält ZIP-Bomb-Limits, GPX-Grenzen und `defusedxml`-Schutz.
- Security-CI umfasst `pip-audit`, Bandit-Gate, externe Spoofing-Negativtests und positive Home-Assistant-Ingress-Simulation.

Ausführliche Details und verbleibende Risiken stehen in `SECURITY.md`.

## Health Auto Export

Laufapp verarbeitet Health Auto Export per REST API, JSON Export Version 2. Unterstützt werden Laufworkout, Start/Ende, Dauer, Distanz, Kalorien, Höhenmeter, mittlere und zeitaufgelöste Herzfrequenz, Running Speed, Running Power, Schrittlänge, vertikale Oszillation, Bodenkontaktzeit, Kadenz, GPS-Route/Höhe sowie Ruhepuls, HRV/SDNN, Gewicht, VO₂max und Schlafdauer.

Empfohlene Lauf-Automation in Health Auto Export:

- Automation: REST API
- Format: JSON, Export Version 2
- Zeitraum: Since Last Sync / Seit letzter Synchronisierung
- Daten: Workouts → Running
- Route Data: On
- Workout Metrics: On
- Workout Metrics Time Grouping: Seconds
- Header: `Authorization: Bearer <dein zufälliger Sync-Token>`

Für Ruhepuls, HRV, Gewicht, VO₂max und Schlaf empfiehlt sich eine zweite, weniger häufige Health-Metrics-Automation.

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

Benutzerdaten liegen im persistenten Home-Assistant-`/data`-Bereich. v0.2.9 benötigt **keine Datenbankschemamigration**; bestehende Läufe, Health-Daten, Bestzeiten, Schuhe, Rennen, Trainingsplan, Einstellungen und Coach-Daten bleiben erhalten.

## OpenAI

Der OpenAI-API-Key bleibt serverseitig in der Home-Assistant-App-Konfiguration und wird nicht an das Browser-Frontend ausgeliefert. Laufapp funktioniert für Plan, Prognosen, Health-Import, Wochenübersicht, Läufe, Schuhe und Rennen vollständig ohne OpenAI-Key.

## Release-Prüfungen

Vor Merge laufen Python-Compilecheck, JavaScript-Syntaxcheck, vollständige Pytest-Regression, 16-Wochen-Marathonsimulation, neun randomisierte Läuferprofile, `pip-audit`, Bandit-Gate, Docker-Build, Health-Auto-Export-E2E, externe Ingress-Spoofing-Negativtests sowie die neue positive Home-Assistant-Ingress-Netzsimulation.

Statisch/isoliert und in Linux/Docker getestet. Die echte Home-Assistant-/Supervisor-/Nabu-Casa-/VPN-/Health-Auto-Export-iPhone-Integration muss nach Installation auf dem Beelink lokal verifiziert werden.

## Lokale Entwicklung

```bash
cd laufapp/app
export LAUFAPP_DATA_DIR=/tmp/laufapp-data
export LAUFAPP_TRANSFER_DIR=/tmp/laufapp-transfer
export LAUFAPP_TRUSTED_INGRESS_ONLY=0
export LAUFAPP_HEALTH_AUTO_EXPORT_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
uvicorn main_v029:app --host 127.0.0.1 --port 8099 --no-proxy-headers
```

Weitere Details: `SECURITY.md`, `RELEASE_NOTES_v0.2.9.md`, `TRAINING_ENGINE.md`, `MIGRATIONS.md`.