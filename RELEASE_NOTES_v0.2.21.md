# Laufapp v0.2.21

## Header-Icon robust über Home Assistant Ingress

Das in v0.2.20 eingeführte freigegebene Lauf-Icon wurde im Header als separate PNG-Datei geladen. In der realen Home-Assistant-/iOS-Ingress-Darstellung erschien dadurch ein defektes Bildsymbol mit Fragezeichen.

v0.2.21 bettet das vom Nutzer freigegebene schwarze/neon-grüne Laufmotiv direkt als PNG-Data-URI in den Header ein. Für das sichtbare Branding ist damit kein separater Bildrequest mehr erforderlich; Pfad-, Ingress- und Browser-Cache-Effekte können den Header nicht mehr auf ein Broken-Image-Symbol zurückfallen lassen.

Die vorhandenen PWA-/Apple-Touch-Assets bleiben erhalten und ihre Cache-Keys werden auf v0.2.21 angehoben. Eine neue Regression dekodiert das eingebettete PNG vollständig, prüft die feste SHA-256-Prüfsumme des freigegebenen 192-Pixel-Motivs und validiert die PNG-Struktur der PWA-Assets einschließlich Chunk-CRC und IDAT-Dekompression.

Keine Datenbankschemamigration. Trainingsengine, Bestzeiten, Apple-Health-Import, Health Auto Export, Nabu-Casa-Transport, Ingress-Sicherheitsgrenzen, persistente Daten und der unabhängig versionierte Home-Assistant-HAE-Relay bleiben funktional unverändert.

Statisch/isoliert und in Linux/Docker zu testen; die reale Home-Assistant-OS-/Ingress-/iOS-Darstellung muss nach Installation lokal verifiziert werden.
