# Sicherheitskonzept – Laufapp v0.1.3

## Lokale Datenhaltung

Trainingsdaten, Wettkämpfe, Schuhe, Health-Metriken, detaillierte Laufmesswerte, GPS-Punkte, Plan und Chat-Historie werden in einer SQLite-Datenbank unter `/data` gespeichert. Dieses Verzeichnis ist vom Programmcode getrennt und bleibt bei normalen Updates derselben Home-Assistant-App erhalten.

## Datenbankmigration

- Datenbankschema wird explizit versioniert.
- Vor jeder Schema-Migration wird eine SQLite-Online-Sicherung unter `/data/backups/` erzeugt und mit `PRAGMA integrity_check` geprüft.
- Migrationen sind additiv; bestehende Nutzertabellen werden nicht gelöscht.
- Schlägt eine Migration fehl, wird die Datenbank aus dem Vorab-Backup wiederhergestellt und der App-Start bricht ab.
- Eine App, deren unterstütztes Schema älter als die vorhandene Datenbank ist, verweigert den Downgrade.

## Apple Health

- Es werden nur für Lauftraining/Recovery relevante Datentypen ausgewertet.
- Importierte Daten werden auf die letzten exakt 24 Kalendermonate begrenzt.
- Upload-Limit: 2 GB; `export.xml` maximal 8 GB entpackte Größe.
- ZIP-Pfade werden validiert; `export.xml` wird aus dem Archiv gestreamt, statt den gesamten Export unkontrolliert zu entpacken.
- Hintergrundjobs speichern die hochgeladene Datei lokal unter `/data/imports/`. Nach erfolgreichem Import wird sie gelöscht. Bei einem Fehler bleibt sie zunächst lokal erhalten, damit der Nutzer den Import wiederholen kann.
- Die eigentlichen Health-Daten werden in einer Datenbanktransaktion importiert. Ein Parser-/Datenfehler hinterlässt keinen halb importierten Datensatz.
- Wiederholte Exporte werden über externe IDs/Fingerprints dedupliziert.
- Zeitreihen und GPS werden nur gespeichert, soweit der Apple-Export sie tatsächlich enthält.

## Local-App → GitHub-App Transfer

Home Assistant vergibt einer Local App und einer App aus einem Custom Repository unterschiedliche persistente `/data`-Bereiche. Für den einmaligen Umzug kann der Nutzer explizit eine Datenbankkopie unter `/share/laufapp-transfer/` vorbereiten.

- Quelle und Ziel werden vor bzw. nach dem Kopieren mit SQLite `integrity_check` geprüft.
- Die GitHub-App übernimmt die Kopie nur in einen **frischen** `/data`-Bereich; eine bereits vorhandene Datenbank wird niemals überschrieben.
- Nach erfolgreicher Übernahme löscht die neue App die Transferkopie und Metadatei.
- Die Transferdateien werden mit restriktiven Dateirechten angelegt.

## OpenAI

- API-Key ausschließlich serverseitig über `/data/options.json` oder `OPENAI_API_KEY`.
- Der Key wird über keine Laufapp-API an das Frontend zurückgegeben.
- Screenshots werden im Speicher verarbeitet und nicht als Bilddatei dauerhaft gespeichert.
- Der Coach erhält einen kompakten Trainingskontext statt pauschal den gesamten 24-Monats-Rohdatensatz.
- Wissenschaftliche Websuche ist separat abschaltbar.
- Das monatliche Budget stoppt weitere KI-Aufrufe, sobald das konfigurierte Limit erreicht ist.

## Trainingsplan-Schutz

Die KI kann keinen Plan direkt verändern. Sie kann nur validierte Vorschläge erzeugen, die der Nutzer explizit übernehmen oder ablehnen muss. Serverseitige Plausibilitätsgrenzen schützen unter anderem vor Doppelbelegung, extremen Distanzsteigerungen und problematischen Abständen belastender Einheiten.

## Netzwerk

Der Port 8099 wird standardmäßig nicht auf dem Home-Assistant-Host veröffentlicht. Im Produktionscontainer ist direkter externer Zugriff blockiert; Home-Assistant-Ingress und der lokale Container-Healthcheck bleiben erlaubt. Damit ist für den normalen Fernzugriff keine FritzBox-Portfreigabe erforderlich.

## Testgrenze

Python/JavaScript, Datenbankmigration, Rollback, Importjobs, Health-Parser, Transferpfad und vollständiger synthetischer Workflow wurden isoliert getestet. Ein echter Docker-/Supervisor-Build von v0.1.3 ist in dieser Entwicklungsumgebung mangels Docker-Daemon nicht möglich und muss beim Update auf dem realen Home-Assistant-OS-Beelink verifiziert werden. Echte OpenAI-Aufrufe mit dem persönlichen API-Key müssen ebenfalls im Zielsystem verifiziert werden.
