# Laufapp v0.2.6 – Health Auto Export

v0.2.6 basiert funktional wieder auf dem getesteten v0.2.5-Stand. Die in v0.3.0 begonnene native iOS-/HealthKit-App wurde vollständig aus der Release-Linie entfernt.

## Neu

- Authentifizierte Schnittstelle für **Health Auto Export JSON Export Version 2**.
- Unterstützt `data.workouts` und `data.metrics` entsprechend der aktuellen HealthyApps-Dokumentation.
- Laufworkouts übernehmen stabile Workout-ID, Start/Ende, Dauer, Distanz, Kalorien, Höhenmeter und mittlere Herzfrequenz.
- Zeitreihen für Herzfrequenz, Running Speed, Running Power, Schrittlänge, vertikale Oszillation und Bodenkontaktzeit werden in `run_samples` gespeichert; dokumentierte `stepCadence` wird als Workout-Kadenzwert übernommen.
- GPS-Routen werden mit Zeitstempel, Breite, Länge und Höhe in `gps_points` gespeichert.
- Gesundheitsmetriken: Ruhepuls, HRV/SDNN, Gewicht, VO2max und Schlafdauer.
- Reimporte sind über Workout-ID und deterministische Sample-/Metric-IDs idempotent.
- Nach Laufimport werden geplante Einheiten gematcht, Apple-Health-Bestzeiten aktualisiert und Prognosen neu berechnet.
- `GET /api/v2/health-auto-export/status` zeigt Konfiguration, letzten Sync und letzte Importstatistik ohne das Secret preiszugeben.

## Sicherheit / Netzwerk

- Die eigentliche Laufapp bleibt unverändert **Home-Assistant-Ingress-only** auf Port 8099.
- Separater minimaler Sync-Gateway auf Port 8100 mit ausschließlich `/health` und `POST /health-auto-export`.
- Port 8100 ist in Home Assistant standardmäßig **nicht veröffentlicht** (`null`) und muss bewusst konfiguriert werden.
- Health Auto Export authentifiziert mit `Authorization: Bearer <Token>` oder `X-Laufapp-Token`.
- Secret liegt als Home-Assistant-App-Option `health_auto_export_token` vom Typ `password` vor; Vergleich erfolgt timing-resistent mit `hmac.compare_digest`.
- Größen- und Mengenlimits schützen vor unbeabsichtigt extremen Payloads.
- Port 8100 darf nicht unverschlüsselt ins Internet weitergeleitet werden. Für Zugriff außerhalb des Heimnetzes ist VPN/Tailscale oder ein korrekt abgesicherter HTTPS-Reverse-Proxy vorgesehen.

## Empfohlene Health-Auto-Export-Konfiguration

- REST API
- JSON
- Export Version 2
- Datumsbereich: **Seit letzter Synchronisierung**
- Workouts: **Running**
- Routendaten einbeziehen: **Ein**
- Workout-Metriken einbeziehen: **Ein**
- Workout-Zeitgruppierung: **Sekunden**
- Separate zweite Automation für Health Metrics: Ruhepuls, HRV, Gewicht, VO2max und Schlaf.

## Kompatibilität

- Keine Datenbankschemamigration.
- Bestehende Daten aus v0.2.5 bleiben unverändert erhalten.
- Manueller Apple-Health-ZIP/XML-Import bleibt vollständig als Fallback verfügbar.
- Die v0.2.5-Oberfläche inklusive Bestzeiten, Prognosefortschritt und kompakter Navigation bleibt unverändert.

## Verifikation

Vor Merge müssen Python-Compilecheck, JavaScript-Syntaxcheck, vollständige Pytest-Regression, 16-Wochen-Simulation, neun randomisierte Läuferprofile, Docker-Build und Docker-Runtime-E2E einschließlich authentifiziertem Health-Auto-Export-Import und Deduplizierung erfolgreich sein.

Statisch/isoliert und in Linux/Docker getestet; reale Health-Auto-Export-/Home-Assistant-/iPhone-Übertragung muss lokal verifiziert werden.
