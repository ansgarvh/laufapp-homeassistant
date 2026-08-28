# Laufapp v0.1.5

Private, mobile-first Lauf-PWA für Home Assistant OS auf dem Beelink Mini S12. Die App verbindet eine lokale Trainings-/Prognoseengine mit Apple-Health-Daten und einem optionalen OpenAI-Coach. Sie ist für genau einen Nutzer ausgelegt.

## Highlights von v0.1.5

- Robuster nativer Apple-Health-Import: Workout-Attribute und verschachtelte `WorkoutStatistics`, aggregierte Diagnose, sichere Reimport-Deduplizierung und Warnung bei verdächtigen Null-Ergebnissen. Recovery-Signale und Prognosen werden nach dem Import beim nächsten Aufruf frisch geladen.
- Wochenübersicht: Wischen im Kalenderkopf wechselt die Woche; geplante Einheiten lassen sich am Griff per Pointer Events verschieben. Freier Tag bedeutet Verschieben, belegter geplanter Tag atomaren Tausch. „Verschieben“ bleibt als zugänglicher Fallback erhalten; abgeschlossene/ausgefallene Einheiten sind geschützt.
- Fortschritt: Wochenkilometer für Monat, 3, 6 oder 12 Monate aus der vollständigen relevanten Laufhistorie statt nur den letzten 100 Läufen; Standard ist 3 Monate.
- Bottom-Navigation: Symbole und Beschriftungen sind rund 18 % größer.

Zeiträume sind rollierende Kalendermonate bis heute; die angebrochene aktuelle Woche wird eingeschlossen. Frühere unbekannte Historie wird nicht erfunden, echte Nullwochen innerhalb des gewählten Bereichs werden gezeigt.

> Die Behebung des konkreten Produktionsimports muss mit dem realen Export auf dem Beelink bestätigt werden. Statisch/isoliert getestet; Home-Assistant-Integration muss auf dem Beelink verifiziert werden.

## Highlights von v0.1.4

- **Große Apple-Health-Uploads über Ingress:** Home Assistant streamt Uploads direkt zur Laufapp. Dadurch können auch große Exportdateien zuverlässig über Ingress hochgeladen werden, ohne die bestehende Ingress-only-Zugriffskontrolle zu ändern.

### Weiterhin enthalten aus v0.1.3

- **Persistente Daten über Updates:** Läufe, Health-Metriken, Schuhe, Wettkämpfe, Trainingsplan, Bestleistungen und Coach-Historie bleiben in `/data/laufapp.sqlite3` erhalten.
- **Versionierte Datenbankmigration:** v0.1.2 wird beim Start automatisch auf Schema 2 migriert. Vor jeder Schemaänderung entsteht eine SQLite-Sicherung unter `/data/backups/`; bei einem Migrationsfehler wird der Vorzustand wiederhergestellt und der App-Start abgebrochen.
- **Apple Health als Hintergrundjob:** Nach abgeschlossenem Upload kann der Browser bzw. die Home-Assistant-App geschlossen oder minimiert werden. Der Beelink verarbeitet die Datei weiter. Status und Ergebnis bleiben abrufbar; ein durch App-Neustart unterbrochener Verarbeitungsjob wird beim nächsten Start erneut aufgenommen.
- **Detaillierte Laufdaten:** Soweit Apple sie exportiert, werden zeitaufgelöste Herzfrequenz, Running Speed, Running Power, Schrittlänge, vertikale Oszillation, Bodenkontaktzeit, abgeleitete Kadenz sowie GPX-/Höhendaten einem Lauf zugeordnet.
- **GitHub-Umzug vorbereitet:** v0.1.3 enthält einen sicheren Einmal-Transfer von der bisherigen lokalen Home-Assistant-App zur späteren GitHub-Repository-App, ohne erneuten Health-Import.
- **GitHub CI vorbereitet:** Compilecheck, JavaScript-Syntaxcheck, vollständige Pytest-Regression und Docker-Build laufen künftig bei Push/PR automatisch.

## Bestehende Funktionen

- **Heute:** aktiver Wettkampf, Zielzeit, Prognose, Zielbewertung, nächste Einheit, Recovery-Signale und offene Coach-Vorschläge.
- **Woche:** vier Trainingseinheiten, Status, Wochenkilometer, RPE + Pace, Verschieben auch in angrenzende Wochen, Planqualitäts- und Longrun-Guardrails.
- **Trainingssteuerung:** Umfang Behutsam/Ausgewogen/Progressiv, Schwierigkeit Komfortabel/Ausgewogen/Anspruchsvoll, maximale Longrun-Distanz und maximaler Longrun-Anteil.
- **Fortschritt:** Prognosen für 5 km, 10 km, Halbmarathon und Marathon mit Unsicherheitsbereich, Wochenkilometer und Leistungsprofil.
- **Apple Health:** exakt 24 Kalendermonate; Läufe, Ruhepuls, HRV, Schlaf, Gewicht und VO₂max; wiederholte Exporte werden dedupliziert.
- **Schuhe:** Stammdaten, Startkilometer und Gesamtlaufstrecke je Schuh.
- **AI Coach:** Chat, Fitness-Screenshot-Auslesen, Laufanalyse und optionaler wissenschaftlicher Wochencheck. Änderungen am Trainingsplan müssen immer bestätigt werden.
- **KI-Budget:** standardmäßig 10 € pro Monat als Kostenschutz-Schätzung.

## Daten bleiben bei normalen Updates erhalten

Der Programmcode liegt im App-Image. Benutzerdaten liegen getrennt in Home Assistants persistentem App-Datenspeicher unter `/data`. Ein normales Update derselben Repository-App ersetzt deshalb den Code, nicht die Datenbank.

Bei einer Änderung des Datenbankschemas führt die App nur definierte additive Migrationen aus. Vorher wird ein konsistentes Backup erzeugt. Ein Downgrade auf eine App mit älterem Datenbankschema wird blockiert, statt die Datenbank zu verändern.

## Einmaliger Übergang von der bisherigen lokalen App zu GitHub

Die bisher manuell installierte App (`local_laufapp`) und eine später aus einem Custom Repository installierte App erhalten von Home Assistant unterschiedliche persistente `/data`-Bereiche. Deshalb enthält v0.1.3 eine kontrollierte Brücke:

1. **v0.1.3 noch einmal manuell als Update der vorhandenen lokalen App installieren und starten.** Dadurch wird die bestehende v0.1.2-Datenbank migriert und gesichert.
2. In **Mehr → App → GitHub-Umzug** auf **Vorbereiten** klicken. Die App erstellt eine integrity-geprüfte Kopie in `/share/laufapp-transfer/`.
3. Das GitHub-Repository einmalig in Home Assistant hinzufügen und die dortige Laufapp installieren.
4. Beim ersten Start der frischen Repository-App wird die vorbereitete Datenbank nur dann übernommen, wenn deren eigener `/data`-Bereich noch keine Laufapp-Datenbank besitzt. Nach erfolgreicher Übernahme wird die Transferkopie gelöscht.
5. **Erst nachdem Läufe/Health/Schuhe in der GitHub-App geprüft wurden**, die alte lokale App entfernen.

Details: `GITHUB_SETUP.md` und `MIGRATIONS.md`.

## OpenAI API

Der API-Key verbleibt serverseitig in der Home-Assistant-App-Konfiguration (`/data/options.json`) und wird nie an das Browser-Frontend ausgeliefert. Ohne API-Key funktionieren Plan, Prognosen, Health-Import, Wochenübersicht, Läufe und Schuhe vollständig.

Standardmodelle: `gpt-5.6-terra` für den Coach und `gpt-5.6-luna` für Screenshot-Extraktion. Wissenschaftliche Websuche ist optional.

## Teststatus v0.1.4

Vor der Paketierung wurden unter anderem ausgeführt:

- Python-Compilecheck für Backend und Tests.
- JavaScript-Syntaxcheck mit Node.
- **31 automatisierte Regressionstests** inklusive vollständigem synthetischem End-to-End-Workflow und statischer Prüfung des Ingress-Streamings.
- Upgrade-Test einer gefüllten v0.1.2-Datenbank auf v0.1.3 mit Datenerhalt und Vorab-Backup.
- Fehler-Injektion in die Migration mit Wiederherstellung des exakten Vorzustands.
- Test des Einmal-Transfers local → GitHub sowie Schutz vor Überschreiben einer bereits vorhandenen Repository-Datenbank.
- Hintergrundimport, Rollback bei defektem Export und Wiederaufnahme eines unterbrochenen Verarbeitungsjobs.
- Detaildaten-Test für Herzfrequenz, Speed, Power, Schrittlänge, vertikale Oszillation, Bodenkontaktzeit, Kadenz und GPX.
- Belastungstest mit einer ca. 100-MB-ZIP und rund 699.000 Health-Records.
- Responsive Renderprüfung der neuen Import-/GitHub-Oberfläche bei 390 px und 320 px ohne horizontalen Overflow.

Compile-, Regressions- und synthetische End-to-End-Tests laufen isoliert und ersetzen keinen Integrationstest auf einer realen Home-Assistant-Installation. Der Docker-Build sowie ein großer Upload über echten Home-Assistant-Ingress müssen deshalb im jeweiligen Release-Prozess separat verifiziert werden. Echte OpenAI-Netzwerkaufrufe mit dem persönlichen API-Key sind ebenfalls nicht Teil der isolierten Tests.

## Lokale Entwicklung

```bash
cd laufapp/app
export LAUFAPP_DATA_DIR=/tmp/laufapp-data
export LAUFAPP_TRANSFER_DIR=/tmp/laufapp-transfer
export LAUFAPP_TRUSTED_INGRESS_ONLY=0
uvicorn main:app --host 127.0.0.1 --port 8099
```
