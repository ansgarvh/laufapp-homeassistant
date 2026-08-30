# Laufapp v0.2.8

Private, mobile-first Lauf-PWA für Home Assistant OS. Laufapp verbindet eine lokale Trainings-/Prognoseengine mit Apple-Health-Daten, Health Auto Export und einem optionalen OpenAI-Coach. Die Anwendung ist für einen einzelnen privaten Nutzer ausgelegt.

## Neu in v0.2.8 – Importdiagnose und Laufzeit-Logging

v0.2.8 baut funktional auf v0.2.7 auf und ändert weder Trainingslogik noch Datenbankschema. Der Fokus liegt ausschließlich darauf, Fehler beim großen Apple-Health-Import und unerwartete Add-on-Neustarts vollständig nachvollziehbar zu machen.

Wesentliche Änderungen:

- **Healthchecks überfluten den normalen Uvicorn-Access-Log nicht mehr:** erfolgreiche `/api/health`- und Gateway-`/health`-Polls werden gefiltert; fehlerhafte Health-Requests und alle anderen API-Aufrufe bleiben sichtbar.
- **Persistente Importdiagnose pro Job:** Phasenwechsel und Fortschritt werden begrenzt als JSONL unter `/data/import_status/<job-uuid>.diagnostics.jsonl` gespeichert. Die Datei bleibt auch nach Abschluss oder Fehler erhalten.
- **Vollständige Background-Job-Tracebacks:** Fehler speichern Exception-Typ, letzte Phase, Fortschritt, Detaildaten und den vollständigen Python-Traceback. Zusätzlich wird der Traceback sofort mit Job-ID und Phase in stderr ausgegeben.
- **Restart-Diagnose:** beim Wiederaufnehmen eines unterbrochenen Imports wird `resumed_after_restart` persistiert.
- **Prozessursache sichtbar:** `run.sh` protokolliert SIGTERM/SIGINT sowie den PID-/Exitstatus des Main- oder Gateway-Prozesses, bevor das Add-on beendet wird.
- **Diagnose-API:** `GET /api/apple-health/import-jobs/{job_id}/diagnostics` liefert die persistenten Diagnoseereignisse über den bestehenden Ingress-geschützten Hauptprozess.
- **Keine Datenbankschemamigration:** bestehende Läufe, Health-Daten, Samples, GPS-Punkte, Bestzeiten, Schuhe, Rennen, Trainingsplan und Einstellungen bleiben unverändert.

## Security-Basis aus v0.2.7

Die Sicherheitsarchitektur aus v0.2.7 bleibt unverändert:

- **Home-Assistant-Ingress gegen Spoofing gehärtet:** Port 8099 vertraut nicht auf `X-Forwarded-For`, `X-Hass-Source` oder `X-Ingress-Path`. In Produktion wird ausschließlich die reale TCP-Quelle des Home-Assistant-Ingress-Proxys (`172.30.32.2`) akzeptiert; Loopback ist nur für `/api/health` erlaubt. Uvicorn läuft ohne Proxy-Header-Vertrauen.
- **Health-Auto-Export-Gateway fail closed:** Port 8100 wird gar nicht gestartet, solange kein ausreichend starker Sync-Token konfiguriert ist.
- **Starker separater Sync-Token:** mindestens 48 zufällige Zeichen, keine Leerzeichen, timing-resistenter Vergleich. Empfohlen: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- **Request-DoS-Schutz:** Authentifizierung vor Body-Lesen, JSON-only, 16-MiB-Streaminglimit, 120-Sekunden-Body-Timeout, Mengenlimits und begrenzte Gateway-Parallelität.
- **Write-only Gateway:** die Sync-Antwort enthält keine Trainingsprognosen, persönlichen Read-Daten oder Versionsinformationen.
- **Replay-/Kollisionsschutz:** idempotenter Reimport, Cross-Source-Deduplizierung und Ablehnung derselben Workout-ID bei widersprüchlichem Start, Distanz oder Dauer.
- **Apple-Health-ZIP/XML gehärtet:** ZIP-Bomb-Limits, Größen-/Dateianzahlgrenzen, GPX-Punkt- und Koordinatenlimits sowie `defusedxml` gegen Entity Expansion/externe XML-Referenzen.
- **Security-CI:** `pip-audit`, Bandit-Gate, gepinnte GitHub-Actions, hostile-ingress-Docker-Test und die bestehende vollständige Regression sind Release-Voraussetzung.

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

## Netzwerk

Port **8099** bleibt ausschließlich Home Assistant Ingress. Er darf nicht als normaler Host-Port veröffentlicht werden.

Port **8100** ist der minimale Health-Auto-Export-Gateway und ist in `config.yaml` ebenfalls standardmäßig **nicht** veröffentlicht. Er startet nur mit einem starken Token. Für Nutzung außerhalb des Heimnetzes muss er über ein **verschlüsseltes VPN (z. B. Tailscale/WireGuard) oder einen korrekt abgesicherten HTTPS-Reverse-Proxy** erreichbar gemacht werden. Eine unverschlüsselte Internet-Portweiterleitung ist ausdrücklich nicht vorgesehen.

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

Benutzerdaten liegen im persistenten Home-Assistant-`/data`-Bereich. v0.2.8 benötigt **keine Datenbankschemamigration**; bestehende Läufe, Health-Daten, Bestzeiten, Schuhe, Rennen, Trainingsplan, Einstellungen und Coach-Daten bleiben erhalten. Diagnose-JSONL-Dateien werden zusätzlich im bereits bestehenden Verzeichnis `/data/import_status` abgelegt.

## OpenAI

Der OpenAI-API-Key bleibt serverseitig in der Home-Assistant-App-Konfiguration und wird nicht an das Browser-Frontend ausgeliefert. Laufapp funktioniert für Plan, Prognosen, Health-Import, Wochenübersicht, Läufe, Schuhe und Rennen vollständig ohne OpenAI-Key.

## Release-Prüfungen

Vor Merge laufen Python-Compilecheck, JavaScript-Syntaxcheck, vollständige Pytest-Regression, 16-Wochen-Marathonsimulation, neun randomisierte Läuferprofile, `pip-audit`, Bandit-Gate, Docker-Build sowie Docker-E2E für Health Auto Export und eine absichtlich feindliche Ingress-Spoofing-Simulation. v0.2.8 ergänzt Regressionstests für persistente Importdiagnose, vollständige Tracebacks, Wiederaufnahme nach Neustart und Shell-Syntax des Prozess-Supervisors.

Statisch/isoliert und in Linux/Docker getestet. Die echte Home-Assistant-/Supervisor-/Nabu-Casa-/VPN-/Health-Auto-Export-iPhone-Integration muss nach Installation auf dem Beelink lokal verifiziert werden.

## Lokale Entwicklung

```bash
cd laufapp/app
export LAUFAPP_DATA_DIR=/tmp/laufapp-data
export LAUFAPP_TRANSFER_DIR=/tmp/laufapp-transfer
export LAUFAPP_TRUSTED_INGRESS_ONLY=0
export LAUFAPP_HEALTH_AUTO_EXPORT_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
uvicorn main_v028:app --host 127.0.0.1 --port 8099 --no-proxy-headers
```

Weitere Details: `SECURITY.md`, `RELEASE_NOTES_v0.2.8.md`, `TRAINING_ENGINE.md`, `MIGRATIONS.md`.