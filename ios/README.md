# Laufapp iOS Companion v0.3.0

Die iOS-App ist eine native Hülle um die bestehende Laufapp und liest Lauf- und Erholungsdaten direkt aus HealthKit. Die bestehende Weboberfläche und das Backend auf Home Assistant bleiben erhalten.

## Architektur

1. Die App speichert ausschließlich die Home-Assistant-URL in UserDefaults und den Long-Lived Access Token im iOS-Keychain (`AfterFirstUnlockThisDeviceOnly`).
2. Über die offizielle Home-Assistant-WebSocket-API (`supervisor/api`) wird eine kurzlebige Ingress-Sitzung erzeugt.
3. Das Laufapp-Panel wird anhand des Ingress-Panels `Laufapp` gefunden; Port 8099 bleibt geschlossen.
4. Die Weboberfläche wird direkt im `WKWebView` über Home-Assistant-Ingress geladen.
5. HealthKit Background Delivery beobachtet neue Lauf-Workouts. Nach einem Lauf werden Workout, Zeitreihen, GPS-Route sowie aktuelle Health-Metriken über dieselbe geschützte Ingress-Sitzung an `/api/v3/healthkit/sync` gesendet.
6. Das Backend dedupliziert anhand der originalen HealthKit-UUIDs. Ein späterer klassischer Apple-Health-Export erzeugt dadurch keine zweite Laufzeile.

## Gelesene Daten

- Workout-Distanz und -Dauer
- zeitaufgelöste Distanz
- Herzfrequenz
- Running Speed
- Running Power
- Kadenz aus StepCount-Intervallen
- Schrittlänge
- vertikale Oszillation
- Bodenkontaktzeit
- GPS-Route und daraus positive Höhenmeter
- Ruhepuls, HRV, Gewicht, VO2max und Schlafdauer

## Lokaler Build auf dem Mac

Voraussetzungen: aktuelles Xcode und XcodeGen (`brew install xcodegen`).

```bash
cd ios
xcodegen generate
open Laufapp.xcodeproj
```

In Xcode unter **Signing & Capabilities** dein persönliches Team auswählen. Für einen kostenlosen Apple-Account ist die direkte Installation auf das eigene iPhone möglich, die Signierung läuft jedoch nach kurzer Zeit ab und muss erneuert werden. Für einen dauerhaften produktiven Betrieb ist das kostenpflichtige Apple Developer Program komfortabler.

Auf dem iPhone anschließend in der Laufapp einmalig eintragen:

- Home-Assistant-Basis-URL, z. B. die Nabu-Casa-URL
- einen persönlichen Long-Lived Access Token aus dem Home-Assistant-Profil

Dann **HealthKit verbinden und testen** auswählen und die Leseberechtigungen erlauben.

## Sicherheitsmodell

Der Add-on-Port 8099 wird nicht veröffentlicht. Der native Client verwendet die von Home Assistant bereitgestellte Ingress-Sitzung und öffnet keinen alternativen unauthentifizierten Datenpfad. Der Long-Lived Access Token liegt nicht in Git, nicht im Add-on und nicht in UserDefaults, sondern im iOS-Keychain.

## Testgrenzen

Das Python-/Docker-Backend wird in der normalen Linux-CI vollständig getestet. Die iOS-Quellen werden zusätzlich auf einem macOS-GitHub-Runner mit XcodeGen und `xcodebuild` für den iOS-Simulator kompiliert. HealthKit Background Delivery, echte Apple-Watch-Daten, Keychain, Nabu-Casa-Ingress und Installation/Signierung auf dem persönlichen iPhone müssen zusätzlich auf realer Apple-Hardware verifiziert werden.
