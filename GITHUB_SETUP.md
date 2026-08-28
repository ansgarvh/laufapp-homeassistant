# Laufapp – einmaliger Wechsel auf GitHub-Updates

Ziel: Nach diesem einmaligen Übergang zeigt Home Assistant neue Laufapp-Versionen direkt als Update an. Die manuelle ZIP-/Studio-Code-Schleife entfällt.

## A. Letztes manuelles Update: v0.1.3

1. Die vorhandene lokale Laufapp auf v0.1.3 aktualisieren.
2. App starten und im Protokoll prüfen, dass sie ohne Migrationsfehler startet.
3. In der Laufapp unter **Mehr → App → GitHub-Umzug** auf **Vorbereiten** klicken.
4. Noch nichts deinstallieren. Die bisherige lokale App bleibt zunächst die Referenzkopie.

Beim Vorbereiten wird die aktuelle Datenbank integrity-geprüft nach `/share/laufapp-transfer/laufapp.sqlite3` kopiert.

## B. GitHub-Repository einmalig anlegen

Auf GitHub ein **öffentliches, leeres Repository** mit dem Namen

`laufapp-homeassistant`

unter dem Benutzer `ansgarvh` anlegen. README, .gitignore und Lizenz beim Erstellen zunächst nicht automatisch hinzufügen, damit das vorbereitete Repository ohne Konflikte hochgeladen werden kann.

Danach kann ChatGPT über die verbundene GitHub-Integration den vorbereiteten Repository-Inhalt veröffentlichen und zukünftige Versionen aktualisieren.

## C. Repository einmalig in Home Assistant hinzufügen

Sobald das Repository befüllt ist:

1. **Einstellungen → Apps → App-Store** öffnen.
2. Menü **⋮ → Repositories** öffnen.
3. `https://github.com/ansgarvh/laufapp-homeassistant` hinzufügen.
4. Store neu laden.
5. Die Laufapp aus diesem Repository installieren.
6. Beim ersten Start übernimmt die frische Repository-App die vorbereitete Transferdatenbank automatisch.

## D. Vor dem Entfernen der alten Local App prüfen

In der neuen Repository-App kontrollieren:

- Läufe vorhanden,
- Apple-Health-Metriken vorhanden,
- Schuhe und Kilometer vorhanden,
- Wettkampf/Zielzeit vorhanden,
- Wochenplan vorhanden,
- Bestleistungen/Prognosen plausibel.

Erst danach die alte Local App stoppen und entfernen.

Hinweis: Home-Assistant-App-Konfigurationsoptionen wie der OpenAI-API-Key gehören nicht zur SQLite-Datenbank. Beim Wechsel auf die neue Repository-App kann der API-Key einmalig erneut eingetragen werden müssen.

## E. Danach

Bei zukünftigen Releases wird nur noch die Versionsnummer im GitHub-Repository erhöht. Home Assistant erkennt die neue Repository-Version und zeigt **Update verfügbar** an. Innerhalb derselben Repository-App bleibt `/data` persistent; Datenbankschemaänderungen laufen über die versionierten Migrationen.
