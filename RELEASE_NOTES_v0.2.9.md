# Laufapp v0.2.9 – Home-Assistant-Ingress-Kompatibilität

Datum: 2026-08-30

## Anlass

Nach Installation von v0.2.8 starteten Hauptprozess und Health-Auto-Export-Gateway sauber, die Weboberfläche war über Home Assistant jedoch nicht erreichbar. Der einzige relevante Unterschied in der Zugriffskette seit der zuvor funktionierenden Linie war die in v0.2.7 verschärfte Ingress-Prüfung: Statt des früheren Header-Fallbacks wurde ausschließlich die TCP-Quelladresse `172.30.32.2` akzeptiert.

Home Assistant dokumentiert `172.30.32.2` weiterhin als normalen Ingress-Proxy. v0.2.9 behält diesen Standard bei, ergänzt aber einen eng begrenzten Kompatibilitätspfad für reale Installationen, bei denen ein anderer Peer aus dem internen Home-Assistant-Netz sichtbar wird.

## Sicherheitsmodell

- `172.30.32.2` bleibt ohne Header-Fallback als dokumentierter Ingress-Proxy zugelassen.
- Andere Peers werden nur akzeptiert, wenn ihre reale TCP-Adresse innerhalb `172.30.32.0/23` liegt.
- Für diesen Fallback sind zusätzlich ein `X-Ingress-Path` unter `/api/hassio_ingress/` und ein Authentifizierungsmarker (`X-Remote-User-Id` oder `X-Hass-Source: core.ingress`) erforderlich.
- Ein externer Client bleibt selbst dann gesperrt, wenn er sämtliche bekannten Ingress-/Forwarding-Header fälscht.
- Uvicorn vertraut weiterhin keine Proxy-Header; die reale TCP-Adresse bleibt maßgeblich.
- Port 8099 bleibt in Home Assistant unveröffentlicht und ausschließlich für Ingress vorgesehen.

## Diagnose

Blockierte Zugriffe erzeugen nun `LAUFAPP_INGRESS_BLOCKED` mit Peer-IP, Pfad und booleschen Angaben zum Vorhandensein der Ingress-Marker. Benutzer-IDs oder Tokens werden nicht geloggt.

## Neue Tests

Die CI simuliert erstmals einen positiven Home-Assistant-Ingress-Pfad in einem eigenen Docker-Netz `172.30.32.0/23`:

1. Quelladresse `172.30.32.2` muss die Weboberfläche erreichen.
2. Ein anderer interner Peer muss mit authentifizierten Ingress-Markern die Weboberfläche erreichen.
3. Derselbe interne Peer ohne Authentifizierungsmarker muss HTTP 403 erhalten.
4. Ein externer/Host-seitiger Client mit gefälschten Ingress-Headern muss HTTP 403 erhalten.

Alle bestehenden Release-Gates für Compile, Regression, Trainingssimulation, Dependency-Audit, Security-Scan, Docker-Build, Health Auto Export und Gateway-Fail-Closed bleiben bestehen.

## Kompatibilität

Keine Datenbankschemamigration. Keine Änderung an Trainingslogik, Prognosen, Apple-Health-Importdaten, GPS/Samples, Bestzeiten oder Health Auto Export.

Statisch/isoliert und in Linux/Docker getestet; die reale Home-Assistant-/Supervisor-Integration muss anschließend auf dem Beelink verifiziert werden.
