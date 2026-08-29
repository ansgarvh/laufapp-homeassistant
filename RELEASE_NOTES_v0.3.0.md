# Laufapp v0.3.0 – Native iOS-/HealthKit-Basis

## Neu

- Native iOS-Companion-App als SwiftUI/WKWebView-Hülle um die bestehende Laufapp.
- Direkter HealthKit-Lesezugriff auf Laufworkouts, GPS-Routen und zeitaufgelöste Laufmetriken.
- Erfasste Laufdaten: Distanz-Zeitreihe, Herzfrequenz, Running Speed, Running Power, Kadenz, Schrittlänge, vertikale Oszillation und Bodenkontaktzeit.
- Zusätzlich Ruhepuls, HRV, Gewicht, VO2max und Schlafdauer.
- HealthKit Background Delivery beobachtet neue Laufworkouts und stößt den Upload automatisch an.
- Sichere Home-Assistant-Anbindung ohne veröffentlichten Add-on-Port: Long-Lived Access Token ausschließlich im iOS-Keychain, Erzeugung einer kurzlebigen Supervisor-Ingress-Sitzung über die offizielle Home-Assistant-WebSocket-API.
- Laufapp-Ingress-Panel wird automatisch anhand des Titels `Laufapp` gefunden.
- Neuer geschützter Backend-Endpunkt `/api/v3/healthkit/sync` sowie Diagnose `/api/v3/healthkit/status`.
- Deduplizierung verwendet die originalen HealthKit-UUIDs, sodass ein späterer klassischer Apple-Health-Export denselben Lauf nicht erneut anlegt.
- Bestehende Tabellen `runs`, `run_samples`, `gps_points` und `health_metrics` werden wiederverwendet; keine Datenbankschemamigration nötig.

## Sicherheit

- Home-Assistant-Ingress-only bleibt unverändert aktiv.
- Port 8099 bleibt standardmäßig nicht veröffentlicht.
- Kein HealthKit- oder Home-Assistant-Token wird im Repository oder im Add-on gespeichert.
- Der iOS-Keychain-Eintrag verwendet `AfterFirstUnlockThisDeviceOnly`, damit Background Delivery nach dem ersten Entsperren arbeiten kann und das Geheimnis nicht auf andere Geräte migriert wird.

## Tests

- Python-Regressionstests für HealthKit-Payload-Validierung, Zeitreihen/GPS/Health-Metriken und idempotenten Re-Import.
- Docker-Runtime-Smoke-Test importiert einen synthetischen nativen HealthKit-Lauf über den neuen API-Pfad.
- Separate macOS-CI erzeugt das Xcode-Projekt mit XcodeGen und kompiliert die App mit `xcodebuild` gegen den iOS-Simulator.
- Reale HealthKit Background Delivery, Apple-Watch-Daten, Nabu-Casa-Sitzung, Keychain und kostenlose/Developer-Program-Signierung müssen zusätzlich auf dem persönlichen iPhone verifiziert werden.
