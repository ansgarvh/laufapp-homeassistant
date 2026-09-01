# Laufapp v0.2.21

## Header-Icon wird jetzt tatsächlich ausgeliefert

v0.2.20 hat das freigegebene Laufmotiv korrekt in `index.html` eingebunden, aber die Laufapp stellte den dort verwendeten Top-Level-Pfad `/icon-192.png` nicht als HTTP-Route bereit. Im Browser führte der Request deshalb zu HTTP 404; Safari zeigte im schwarzen Header-Feld einen Bildfehler-Platzhalter mit Fragezeichen.

v0.2.21 ergänzt explizite, schemafreie `image/png`-Routen für `/icon-192.png` und `/icon-512.png`. Der Header verwendet für die 192-Pixel-Datei zusätzlich `?v=0.2.21`, damit ein zuvor fehlgeschlagener Abruf nicht aus einem Browser-/WebView-Cache wiederverwendet wird.

Neue Regressionstests rufen exakt die Browser-URL auf, verlangen HTTP 200 und `image/png` und validieren die PNG-Struktur inklusive Chunk-CRC und IDAT-Dekompression. Der bestehende Apple-Touch-Icon-Pfad wird ebenfalls auf Erreichbarkeit und Dekodierbarkeit geprüft.

Keine Datenbankschemamigration. Trainingsengine, Bestzeiten, Apple Health, Health Auto Export, Nabu-Casa-/Ingress-Security, persistente Daten und der unabhängig versionierte Home-Assistant-HAE-Relay bleiben funktional unverändert.

Statisch/isoliert und in Linux/Docker zu testen; die reale Darstellung über Home Assistant OS/Ingress und iOS muss nach Installation lokal verifiziert werden.
