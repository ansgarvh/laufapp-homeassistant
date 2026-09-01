# Laufapp v0.2.21

## Header-Icon robust über Home Assistant Ingress

Das in v0.2.20 eingeführte freigegebene Lauf-Icon wurde im Header als separate PNG-Datei geladen. In der realen Home-Assistant-/iOS-Ingress-Darstellung erschien dadurch ein defektes Bildsymbol mit Fragezeichen.

v0.2.21 bettet das vom Nutzer freigegebene schwarze/neon-grüne Laufmotiv direkt als PNG-Data-URI in den Header ein. Für das sichtbare Branding ist damit kein separater Bildrequest mehr erforderlich; Pfad-, Ingress- und Browser-Cache-Effekte können den Header nicht mehr auf ein Broken-Image-Symbol zurückfallen lassen.

Die verschärfte Asset-Regression hat zusätzlich nachgewiesen, dass das in v0.2.20 ausgelieferte 512-Pixel-PWA-PNG eine ungültige PNG-CRC enthielt. Dieses defekte Asset wird in v0.2.21 entfernt. Das PWA-Manifest verwendet stattdessen ein textbasiertes, selbst enthaltenes SVG-Lauficon (`sizes: any`) sowie die bewährte 192-Pixel-PNG als Fallback; das vorhandene Apple-Touch-Icon bleibt erhalten. Die Regression dekodiert das eingebettete Header-PNG vollständig, prüft dessen feste SHA-256-Prüfsumme, validiert die tatsächlich referenzierten PNGs einschließlich Chunk-CRC und IDAT-Dekompression und prüft das SVG auf gültige, externe Ressourcen freie Struktur.

Keine Datenbankschemamigration. Trainingsengine, Bestzeiten, Apple-Health-Import, Health Auto Export, Nabu-Casa-Transport, Ingress-Sicherheitsgrenzen, persistente Daten und der unabhängig versionierte Home-Assistant-HAE-Relay bleiben funktional unverändert.

Statisch/isoliert und in Linux/Docker zu testen; die reale Home-Assistant-OS-/Ingress-/iOS-Darstellung muss nach Installation lokal verifiziert werden.
