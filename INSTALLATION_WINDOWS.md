# Laufapp v0.1.3 – letztes manuelles Home-Assistant-Update

Diese Anleitung gilt für den Übergang von der aktuell installierten v0.1.2-Local-App auf v0.1.3. Danach soll auf GitHub-Updates gewechselt werden (`GITHUB_SETUP.md`).

## 1. ZIP nach `/config` hochladen

`laufapp-v0.1.3-home-assistant.zip` in Studio Code Server nach `/config` hochladen.

## 2. Quellordner ersetzen

Laufapp in Home Assistant stoppen. Im Studio-Code-Terminal:

```bash
rm -rf /addons/laufapp
cd /addons
unzip /config/laufapp-v0.1.3-home-assistant.zip
```

Prüfen:

```bash
grep 'version:' /addons/laufapp/config.yaml
```

Erwartet: `version: "0.1.3"`.

## 3. Home Assistant aktualisieren

**Einstellungen → Apps → App-Store → ⋮ → Nach Updates suchen**. Danach die vorhandene Laufapp auf v0.1.3 aktualisieren.

Beim ersten Start migriert die App die bestehende Datenbank automatisch. Vorher wird unter `/data/backups/` eine Sicherung angelegt. Bestehende Health-Daten müssen nicht erneut importiert werden.

## 4. Nach Start prüfen

- Protokoll ohne Migrationsfehler,
- Heute/Woche öffnen,
- einige vorhandene Läufe kontrollieren,
- Apple-Health-Status unter Mehr kontrollieren,
- Schuhe/Wettkampf prüfen.

Dann **Mehr → App → GitHub-Umzug → Vorbereiten** ausführen und mit `GITHUB_SETUP.md` fortfahren.
