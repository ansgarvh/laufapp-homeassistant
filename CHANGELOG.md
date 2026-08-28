# Laufapp Changelog

## v0.2.0 – 2026-08-28

- Mehrere zukünftige Wettkämpfe können unter **Einstellungen → Rennen** gepflegt, bearbeitet und gelöscht werden. Bestehende v0.1.9-Wettkämpfe werden kompatibel als A-Rennen behandelt.
- **A-Rennen** steuern den Trainingsblock vollständig; das jeweils nächste zukünftige A-Rennen ist der Planfokus, nach dessen Rennwoche übernimmt automatisch das nächste A-Rennen.
- **B-Rennen** lösen keinen Taper und keine Änderung der vorherigen Trainingswochen aus. In ihrer Rennwoche ersetzen sie ausschließlich den Longrun; die übrigen Trainingseinheiten bleiben in einer normalen konfliktfreien Woche unverändert.
- Jedes Rennen besitzt eine eigene Zielzeit. Direkt darunter zeigt Laufapp dezent die datenbasierte aktuelle Zeitprognose inklusive Prognosebereich an; die Empfehlung kann optional als Ziel übernommen werden.
- Trainingsumfang erhält eine echte rennrelative Blockprogression: aufeinanderfolgende Build-/Specific-Belastungswochen können innerhalb eines Blocks ansteigen, Recovery, Nutzerobergrenzen, Detraining und Taper bleiben harte Gegenbedingungen.
- Absolvierte, mit einem realen Lauf verknüpfte Einheiten können direkt aus der Wochenansicht einem Schuh zugeordnet werden. Die vorhandene `runs.shoe_id`-Zuordnung wird verwendet, sodass die Kilometerbilanz des Schuhs sofort mit dem real gelaufenen Umfang steigt. Die bestehende Zuordnung im Fortschritt-Tab bleibt erhalten.
- Keine neue Datenbankschemaversion nötig: A/B-Klassifikation wird kompatibel in den bestehenden persistenten Einstellungen gespeichert; vorhandene Läufe, Health-Daten, Schuhe, Trainingspläne und manuelle Änderungen bleiben erhalten.
- Home-Assistant-Ingress, `ingress_stream`, persistente SQLite-Daten und die v0.1.9-Schutzmechanismen für manuelle/absolvierte Workouts bleiben erhalten.

## v0.1.9 – 2026-08-28

- „Plan neu berechnen“ aus Einstellungen funktioniert auch ohne vorher geöffneten Woche-Tab; ein `start=null` wird als aktuelle Kalenderwoche behandelt statt als 422-Fehler mit `[object Object]` im Frontend zu enden.
- Die Wochenplanung repariert eindeutig veraltete v0.1.8-Engine-Dubletten, wenn auf demselben Tag bereits eine absolvierte, verknüpfte oder manuell geschützte Einheit vorhanden ist, und erzeugt auf belegten Tagen keine zusätzliche automatische Einheit.
- Bei einer Neuberechnung berücksichtigt der automatisch erzeugte Restplan bereits geschützte Wochenkilometer. Automatische Einheiten werden bei Bedarf skaliert, statt die eingestellte Wochenobergrenze durch Addition auf absolvierte/manuelle Einheiten zu überschreiten.
- Fortschritt: Datumsbeschriftungen der Wochen stehen wieder im reservierten Bereich unter den Balken und überlagern das Diagramm nicht mehr.
- Woche: Drag-Griffe bleiben bewusst nur an geplanten, verschiebbaren Einheiten sichtbar; absolvierte/geschützte Zeilen behalten nun dennoch dieselbe Spaltenausrichtung.
- Keine Datenbankschemaänderung; Apple-Health-Daten, Läufe, Schuhe, Wettkämpfe, Einstellungen und manuelle Planänderungen bleiben erhalten.

## v0.1.8 – 2026-08-28

- Dedizierte mobile Einstellungen-Navigation mit persistenten, serverseitig validierten Planungslimits.
- Deterministische Engine unterstützt 3–7 Lauftage, 1–3 Qualitätseinheiten, automatische/manuelle Wochenobergrenze und distanzabhängige Longrun-Obergrenzen (Marathon: 35 km). Intensive Longruns verbrauchen dabei ein Qualitätsbudget.
- Planneuberechnung aus Woche entfernt und nach Einstellungen verschoben; stale Hinweis verlinkt dorthin.
- Produktionsfehler behoben: „Wochenumfang“, Longrun und Qualität vergleichen jetzt dieselbe einzelne Startwoche; zuvor wurden alle Wochen des Refresh-Fensters addiert.
- „Aktuelle Woche“ ergänzt; bestehender Request-Zähler schützt weiterhin vor verspäteten Wochenantworten.
- Additive Settings-Schlüssel benötigen keine Tabellenschema-Migration und bewahren bestehende Werte.

## v0.1.7 – 2026-08-28

- Robuste etablierte Wochenlast aus acht abgeschlossenen Wochen; Teilwoche ist nur Kontext, echter Rückgang wird separat erkannt.
- Rennrelative Build/Specific/Peak/Taper/Race-Phasen, blockbasierte Recovery und periodisierte Qualität/Marathon-Long-Runs.
- Explizite Planfrische und transaktionale Neuberechnung mit Diff; kein stilles Überschreiben nach Health-Import.
- Schema 4 schützt manuell verschobene/getauschte, Coach-geänderte, vergangene, verknüpfte und absolvierte Einheiten.
- Planbasis und Long-Run-Begründung machen die lokale, LLM-unabhängige Verschreibung nachvollziehbar.

## v0.1.6 – 2026-08-28

- Apple-Health-Diagnose trennt erwartete Ausschlüsse außerhalb des 24-Monats-Zeitraums von ungültigen Workouts und zeigt erkannte, vorhandene und neue Health-Metriken verständlich an.
- Der bestehende Uploadbereich akzeptiert ZIP und `export.xml` nun auch per Drag & Drop; Dateiauswahl und Drop verwenden dieselbe Ingress-Streaming-/Job-Pipeline.
- Optionaler, einmal bestätigter Ersatzmodus tauscht ausschließlich Apple-Health-Daten in einer Transaktion aus. Fehler rollen vollständig zurück; RPE, Notizen, Schuh und eindeutige Workout-Verknüpfungen werden anhand stabiler Apple-IDs wiederhergestellt.
- Workout-Drag & Drop erkennt nun neben der kompakten Tagesleiste auch die tatsächlich übereinander abgelegten Workout-Karten als Drop-Ziele; Backend-Move/-Swap bleibt atomar und schützt abgeschlossene/ausgefallene Einheiten.
- Wochenkilometer-Balken sind per Klick/Tap auswählbar und zeigen Zeitraum sowie Kilometer in einem dezent rot akzentuierten Overlay.
- Fortschritt ergänzt die kalendergenauen Zeiträume „Dieses Jahr“ und „Letztes Jahr“; grenzüberschreitende ISO-Wochen enthalten ausschließlich Läufe des gewählten Kalenderjahres. Lange Zeiträume beschriften die weiterhin wöchentlichen Balken sparsamer.
- Additive Schema-3-Migration speichert den Ersatzmodus eines Hintergrundjobs restartfest und erstellt vorher das bestehende integrity-geprüfte Backup.
- Statisch/isoliert getestet; Home-Assistant-Integration muss auf dem Beelink verifiziert werden.

## v0.1.5 – 2026-08-28

- Apple-Health-Workouts werden zusätzlich aus nativen `WorkoutStatistics` (Distanz, Dauer, Energie) gelesen; Endzeit dient konservativ als Dauer-Fallback.
- Persistente Importergebnisse enthalten aggregierte Lauf-, Metrik-, Sample-, Routen- und Ablehnungsdiagnosen sowie Success/Warning-Klassifikation.
- Health-Ergebnisansicht unterscheidet „0 neu“ von „0 gefunden“ und zeigt v0.1.4-Legacyfelder weiterhin.
- Wochenwechsel per Swipe, race-sicheres Rendering und Pointer-Drag am Griff; freie Tage verschieben, belegte geplante Tage tauschen atomar.
- Wochenkilometer-API und Auswahl für 1/3/6/12 Monate ohne 100-Läufe-Limit.
- Bottom-Navigation um rund 18 % vergrößert.
- Keine Schemaänderung; persistente SQLite-Daten und Ingress-Schutz bleiben unverändert.

## v0.1.4 – 2026-08-28

### Behoben
- Home Assistant Ingress streamt große Apple-Health-Uploads nun direkt zur Laufapp, statt sie vor der Weiterleitung vollständig zu puffern.
- Die bestehende Ingress-only-Zugriffskontrolle und der standardmäßig nicht veröffentlichte Webport bleiben unverändert.
- Ein statischer Regressionstest stellt sicher, dass Ingress-Streaming in der Home-Assistant-App-Konfiguration aktiviert bleibt.

## v0.1.3 – 2026-08-28

### Datenhaltung & Updates
- Explizites Datenbankschema (`PRAGMA user_version`) und versionierte Migrationen eingeführt.
- Bestehende v0.1.0–v0.1.2-Datenbanken werden additiv auf Schema 2 migriert; Läufe, Health-Daten, Schuhe, Wettkämpfe, Trainingsplan, Bestleistungen und Coach-Daten bleiben erhalten.
- Vor Schema-Migration wird eine integrity-geprüfte SQLite-Sicherung unter `/data/backups/` erzeugt.
- Bei Migrationsfehler wird der Vorzustand aus dem Backup wiederhergestellt und der Start abgebrochen; Downgrades auf ein älteres Schema werden blockiert.
- Einmalige, integrity-geprüfte Datenbrücke über `/share/laufapp-transfer/` für den Wechsel von der bisherigen Local App zur späteren GitHub-Repository-App ergänzt. Vorhandene Repository-Daten werden niemals überschrieben.

### Apple Health
- Apple-Health-Import auf persistenten serverseitigen Hintergrundjob umgestellt.
- Nach abgeschlossenem Upload kann Browser/Home-Assistant-App geschlossen oder minimiert werden; Status bleibt persistent abrufbar.
- Ein beim App-Neustart unterbrochener Verarbeitungsjob wird beim nächsten Start erneut aufgenommen; deduplizierte Inserts und transaktionaler Health-Import verhindern Doppel-/Teildaten.
- Klare Phasen- und Prozentanzeige im Bereich **Mehr → Apple Health**.
- Fehlgeschlagene Jobs können erneut gestartet werden, solange die lokale Importdatei vorhanden ist.
- Zeitaufgelöste Laufmetriken ergänzt: Herzfrequenz, Running Speed, Running Power, Schrittlänge, vertikale Oszillation und Bodenkontaktzeit; Kadenz wird aus zeitgebundenen Step-Count-Samples abgeleitet.
- GPX-Routen werden – soweit im Apple-Export vorhanden – dem passenden Lauf zugeordnet; GPS-Punkte und Höhenprofil werden gespeichert, fehlende Höhenmeter können aus dem Profil abgeleitet werden.
- Neuer Detail-Endpunkt für Sample-Zusammenfassung und GPS-Punktzahl je Lauf.

### GitHub / Release-Prozess
- Repository-Metadaten (`repository.yaml`) für ein Home-Assistant-Custom-Repository ergänzt.
- GitHub-Actions-CI ergänzt: Python 3.13, Compilecheck, Node-Syntaxcheck, vollständige Regressionstests und Docker-Build.
- Tests sind self-contained; der v0.1.2-Migrationsfixture liegt im Repository und benötigt keinen alten lokalen Quellbaum.
- Docker-COPY-Quellen werden weiterhin statisch gegen den Build-Kontext geprüft.

### Tests
- 30 automatisierte Tests plus separater ca. 100-MB-/699k-Record-Importtest.
- 390-px- und 320-px-Renderprüfung für die neue Import-/Transfer-Oberfläche.

## v0.1.2 – 2026-08-28

### Behoben
- Home-Assistant-Cloud/Ingress-Zugriff repariert: Die Ingress-Sicherheitsprüfung erkennt nun die von Home Assistant Core gesetzten Header `X-Hass-Source: core.ingress` und `X-Ingress-Path`, statt sich auf die durch Proxy-Header umgeschriebene Client-IP zu verlassen.
- Direkter Zugriff bleibt blockiert; der Webport ist weiterhin nicht auf den Home-Assistant-Host veröffentlicht.
- Regressionstest für echten Ingress-Headerpfad, blockierten Direktzugriff und lokalen Healthcheck ergänzt.

## v0.1.1 – 2026-08-28

### Behoben
- Home-Assistant-Docker-Build repariert: `requirements.txt` liegt im Root der lokalen App und wird nun von dort in das Image kopiert.
- Neuer statischer Release-Test prüft die `COPY`-Quellen des Dockerfiles.

## v0.1.0 – 2026-08-28

Erstes funktionsfähiges privates Release mit mobile-first PWA, Heute/Woche/Fortschritt/Coach/Mehr, vier Trainingstagen, Zielzeitsteuerung, Apple-Health-Basisimport, Schuhtracking, Prognosen und bestätigungspflichtigem AI-Coach.