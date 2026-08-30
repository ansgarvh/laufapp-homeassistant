# Laufapp v0.2.6

Private, mobile-first Lauf-PWA für Home Assistant OS. Laufapp verbindet eine lokale Trainings-/Prognoseengine mit Apple-Health-Daten und einem optionalen OpenAI-Coach. Die Anwendung ist für einen einzelnen privaten Nutzer ausgelegt.

## Neu in v0.2.6

v0.2.6 baut wieder auf dem vollständig getesteten **v0.2.5-Stand** auf. Die zwischenzeitlich entwickelte native iOS-/HealthKit-App aus v0.3.0 gehört nicht mehr zur Release-Linie. Stattdessen übernimmt **Health Auto Export** die HealthKit-Brücke vom iPhone zur Laufapp.

Health Auto Export kann per REST API JSON Export Version 2 senden. Laufapp verarbeitet dabei:

- Laufworkouts mit stabiler Workout-ID, Start/Ende, Dauer, Distanz, Kalorien, Höhenmetern und mittlerer Herzfrequenz
- zeitaufgelöste Herzfrequenz
- Running Speed
- Running Power
- Schrittlänge
- vertikale Oszillation
- Bodenkontaktzeit
- dokumentierte Workout-Kadenz (`stepCadence`)
- GPS-Route mit Zeitstempel und Höhe
- Ruhepuls
- HRV/SDNN
- Gewicht
- VO₂max
- Schlafdauer

Reimporte sind idempotent. Nach einem Laufimport werden geplante Einheiten gematcht, Apple-Health-Bestzeiten aktualisiert und Prognosen neu berechnet.

## Empfohlene Health-Auto-Export-Konfiguration

Für Laufdaten:

- Automation Type: **REST API**
- Export Format: **JSON**
- Export Version: **Version 2**
- Date Range: **Since Last Sync / Seit letzter Synchronisierung**
- Data Type: **Workouts**
- Workout: **Running**
- Include Route Data: **On**
- Include Workout Metrics: **On**
- Workout Metrics Time Grouping: **Seconds**
- Header: `Authorization: Bearer <dein Token>`

Für allgemeine Gesundheitsdaten empfiehlt sich eine zweite Automation mit **Health Metrics** und nur den benötigten Metriken: Resting Heart Rate, Heart Rate Variability, Weight/Body Mass, VO₂ Max und Sleep Analysis.

Health Auto Export weist selbst darauf hin, dass iOS Hintergrundausführungen nicht zu einem garantierten Zeitpunkt startet und Health-Daten bei gesperrtem iPhone nicht zugänglich sind. Der Sync ist daher automatisch, aber nicht zwingend unmittelbar nach dem Stoppen eines Laufs.

## Netzwerk und Sicherheit

Die eigentliche Laufapp bleibt weiterhin **Home-Assistant-Ingress-only**.

- Port **8099**: Laufapp UI/API über Home Assistant Ingress; direkte Veröffentlichung standardmäßig deaktiviert.
- Port **8100**: separater minimaler Health-Auto-Export-Gateway mit ausschließlich `/health` und `POST /health-auto-export`; standardmäßig ebenfalls nicht veröffentlicht.
- Der Health-Auto-Export-Endpunkt benötigt zwingend ein Secret aus der Home-Assistant-App-Option `health_auto_export_token`.
- Unterstützt werden `Authorization: Bearer <Token>` und `X-Laufapp-Token: <Token>`.
- Das Token wird timing-resistent mit `hmac.compare_digest` verglichen.
- Für Payload-Größe, Workout-Anzahl, Zeitreihen und GPS-Punkte gelten Schutzlimits.

**Port 8100 niemals unverschlüsselt ins Internet weiterleiten.** Für Zugriff außerhalb des Heimnetzes ist VPN/Tailscale oder ein korrekt abgesicherter HTTPS-Reverse-Proxy vorgesehen. Für den ersten lokalen Test kann Port 8100 bewusst auf einen Host-Port gemappt und im Heimnetz verwendet werden.

## Bestehende Funktionen aus v0.2.5

- **Heute:** Planfokus, Zielzeit, Prognose, nächste Einheit, Recovery-Signale und Coach-Vorschläge
- **Woche:** 3–7 konfigurierbare Lauftage, Verschieben/Tauschen, Status, Wochenkilometer und Planbegründungen
- **Rennen:** mehrere A-/B-Rennen mit eigener Zielzeit
- **Trainingssteuerung:** wissenschaftlich orientierte Marathonperiodisierung, Workout-Variation, Deload/Taper, Longrun-/Qualitätsbudget und Planungsaggressivität
- **Fortschritt:** Prognosen für 5 km, 10 km, Halbmarathon und Marathon
- **Bestzeiten:** manuelle Leistungsanker plus automatische Erkennung aus Apple-Health-Läufen
- **Apple Health:** manueller ZIP/XML-Import der letzten 24 Monate bleibt vollständig als Fallback erhalten
- **Detaillierte Laufdaten:** HR, Speed, Power, Schrittlänge, vertikale Oszillation, Bodenkontaktzeit, Kadenz soweit vorhanden, GPS/Höhe
- **Schuhe:** Stammdaten und Kilometerbilanz
- **AI Coach:** optionaler Chat, Screenshot-Auswertung und bestätigungspflichtige Planänderungen

## Persistenz und Migration

Benutzerdaten liegen in Home Assistants persistentem `/data`-Bereich, der Programmcode im Container-Image. Ein normales Update derselben Repository-App ersetzt daher nicht die SQLite-Datenbank.

v0.2.6 benötigt **keine neue Datenbankschemaversion**. Bestehende v0.2.5-Läufe, Health-Daten, Bestzeiten, Schuhe, Rennen, Trainingsplan, Einstellungen und Coach-Daten bleiben erhalten.

Der manuelle Apple-Health-ZIP/XML-Import bleibt bewusst bestehen. Health Auto Export ist die kontinuierliche Schnittstelle für neue Daten; der Export-Import bleibt Backup-, Historien- und Diagnosepfad.

## OpenAI API

Der OpenAI API-Key bleibt serverseitig in der Home-Assistant-App-Konfiguration (`/data/options.json`) und wird nicht an das Browser-Frontend ausgeliefert. Die Laufapp funktioniert für Plan, Prognosen, Health-Import, Wochenübersicht, Läufe, Schuhe und Rennen auch ohne OpenAI-Key.

## Tests

Die CI prüft vor einem Release:

- Python-Compilecheck
- JavaScript-Syntax
- vollständige Pytest-Regression
- 16-Wochen-Marathonsimulation
- neun reproduzierbar randomisierte Läuferprofile
- Docker-Build
- Docker-Runtime-Smoke-Test
- Start von Laufapp und separatem Health-Auto-Export-Gateway
- abgelehnten unauthentifizierten Sync
- authentifizierten synthetischen JSON-v2-Workoutimport
- Herzfrequenz-, Power- und GPS-Übernahme
- Health-Metrik-Übernahme
- wiederholte Zustellung ohne Duplikate

Statisch/isoliert und in Linux/Docker getestet; reale Health-Auto-Export-/Home-Assistant-/iPhone-Übertragung muss lokal verifiziert werden.

## Lokale Entwicklung

```bash
cd laufapp/app
export LAUFAPP_DATA_DIR=/tmp/laufapp-data
export LAUFAPP_TRANSFER_DIR=/tmp/laufapp-transfer
export LAUFAPP_TRUSTED_INGRESS_ONLY=0
export LAUFAPP_HEALTH_AUTO_EXPORT_TOKEN=dev-secret
uvicorn main_v026:app --host 127.0.0.1 --port 8099
```

Optional parallel für den dedizierten Sync-Gateway:

```bash
uvicorn health_auto_export_gateway:app --host 127.0.0.1 --port 8100
```

Weitere Details stehen in `RELEASE_NOTES_v0.2.6.md`, `TRAINING_ENGINE.md`, `MIGRATIONS.md` und `SECURITY.md`.
