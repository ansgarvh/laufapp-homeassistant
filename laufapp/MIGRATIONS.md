# Laufapp – Datenbankmigrationen

## Grundsatz

Benutzerdaten gehören nicht zum App-Image. Die produktive Datenbank liegt unter `/data/laufapp.sqlite3`. Normale Updates derselben Home-Assistant-App behalten `/data` bei.

## Schema 1

Implizites Schema der Versionen v0.1.0 bis v0.1.2 ohne gesetztes `PRAGMA user_version`.

## Schema 2 – ab v0.1.3

Ergänzt:

- `import_jobs` für persistente Hintergrundimporte,
- `run_samples` für zeitaufgelöste Laufmetriken,
- `gps_points` für Routen/Höhenprofile,
- `migration_log` für erfolgreich ausgeführte Migrationen,
- explizites `PRAGMA user_version=2` und Setting `schema_version=2`.

Die Migration 1 → 2 ist additiv und löscht keine bestehenden Tabellen oder Nutzerdaten.

## Sicherheitsablauf

1. vorhandenes Schema erkennen,
2. Downgrade-Situation ablehnen,
3. SQLite-Online-Backup erzeugen,
4. Backup auf Integrität prüfen,
5. additive Migration ausführen,
6. Versionsmarker setzen,
7. finale Datenbank auf Integrität prüfen.

Schlägt Schritt 5–7 fehl, wird aus der Sicherung wiederhergestellt und der App-Start abgebrochen.

## Schema 4 – ab v0.1.7

Ergänzt additive Workout-Metadaten `manual_override`, `modified_by`, `generation_version` und `plan_generation_id`. Bestehende Workouts gelten weiterhin als Engine-Einheiten; Status, Verknüpfungen und sämtliche Nutzerdaten bleiben erhalten. Die Migration 3 → 4 verwendet den bestehenden Backup-, Integritäts- und Rollback-Ablauf.
