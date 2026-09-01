# Laufapp v0.2.20

## Neues freigegebenes Laufapp-Icon

Das bisher im Header per CSS gezeichnete abstrakte Laufzeichen wurde durch das freigegebene schwarze Icon mit neon-grünem Läufer und drei horizontalen Bewegungslinien ersetzt.

Dasselbe Motiv wird jetzt konsistent für den Header, die 192-/512-Pixel-PWA-Icons und das Apple-Touch-Icon verwendet. Der Service-Worker-Cache und die Icon-URLs sind auf v0.2.20 cache-busted, damit ältere Browser-/PWA-Caches das bisherige Symbol nicht weiterverwenden.

Das zuvor in `index.html` referenzierte, aber nicht vorhandene `apple-touch-icon.png` ist nun tatsächlich vorhanden.

Keine Datenbankschemamigration. Trainingsengine, Bestzeiten, Apple-Health-Import, Health Auto Export, Nabu-Casa-Transport, Ingress-Schutz, persistente Daten und der unabhängig versionierte Home-Assistant-HAE-Relay bleiben funktional unverändert.

Statisch/isoliert und in Linux/Docker zu testen; die reale Home-Assistant-OS-/Ingress-/PWA-Darstellung und ein gegebenenfalls bereits installiertes Homescreen-Icon müssen auf dem Zielsystem lokal verifiziert werden.
