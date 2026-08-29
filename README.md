# Laufapp v0.2.2

Private, mobile-first Lauf-PWA für Home Assistant OS auf dem Beelink Mini S12. Die App verbindet eine lokale Trainings-/Prognoseengine mit Apple-Health-Daten und einem optionalen OpenAI-Coach. Sie ist für genau einen Nutzer ausgelegt.

## Highlights von v0.2.2

- **Fehlende v0.2-Einstellungen behoben:** Der `/assets`-Mount zeigte bislang auf `static/` statt auf `static/assets/`. Dadurch wurden u. a. `v020.js` und `v020_science.js` im realen Add-on mit HTTP 404 beantwortet. Die Basis-UI funktionierte weiter, aber A-/B-Rennen und Planungsaggressivität waren unsichtbar.
- **A-/B-Rennen werden jetzt real ausgeliefert:** Die bereits vorhandene Mehrfach-Rennverwaltung unter **Einstellungen → Rennen** wird nun aus dem korrekten statischen Verzeichnis geladen.
- **Planungsaggressivität wird jetzt real ausgeliefert:** Unter **Einstellungen** stehen **Konservativ**, **Moderat** und **Aggressiv** zur Verfügung. Die Auswahl steuert die vorhandenen Profile `gradual`, `steady` und `progressive`; harte Wochen-/Longrun-Limits, Recovery, Deload, Taper und Qualitätsbudget bleiben bindend.
- **Cache-Invalidierung für Home Assistant/iOS:** relevante Frontend-Assets tragen `?v=0.2.2`, der PWA-Cache heißt `laufapp-v0.2.2`, und Frontend-Antworten werden mit `Cache-Control: no-store, max-age=0` ausgeliefert.
- **Runtime-Regression erweitert:** Der Docker-Smoke-Test prüft jetzt nicht nur `/api/health`, sondern lädt im gestarteten Container die echten v0.2-JavaScript-Assets und prüft A-/B-Rennlogik, Aggressivitätsoptionen sowie `/api/v2/races` und `/api/settings`.
- **Keine Datenbankschemamigration:** bestehende Läufe, Apple-Health-Daten, Rennen, Schuhe, Coach-Daten und Einstellungen bleiben erhalten.

## Highlights von v0.2.1

- **Wochenziel konsistent:** Ein nachgelagerter Longrun-Anteils-Guardrail kann eine vollständig automatisch erzeugte Woche nicht mehr unbemerkt deutlich unter das zuvor berechnete Wochenziel drücken.
- **Longrun-Anteil als Guardrail statt pauschaler Abschneider:** Die normale 45-%-Orientierung bleibt konservativer Belastungsrahmen. Ein bewusst strengerer Nutzerwert bleibt bindend; reale Longrun-Historie und `max_long_run_km` werden berücksichtigt.
- **Kilometer-Rückverteilung:** Wenn ein tatsächlich bindender Guardrail in einer gemischten/geschützten Woche Kilometer entfernt, können diese soweit sinnvoll ausschließlich auf flexible zukünftige Easy Runs verteilt werden.
- **Planbasis klarer:** `Aktueller Umfang` wurde zu **Trainingsbasis**, `Geplant` zu **Wochenziel** präzisiert.
- **Drei Progressionsstufen:** Konservativ / Moderat / Aggressiv basieren auf der bereits vorhandenen deterministischen Blockprogression statt auf einem pauschalen Kilometeraufschlag.

## Highlights von v0.2.0

- **Mehrere Rennen:** Unter **Einstellungen → Rennen** können mehrere zukünftige Wettkämpfe mit Name, Datum, Distanz, Typ und eigener Zielzeit verwaltet werden.
- **A-Rennen:** steuern die vollständige Trainingsperiodisierung. Das nächste zukünftige A-Rennen ist der Planfokus; nach seiner Rennwoche übernimmt automatisch das nächste A-Rennen.
- **B-Rennen:** lösen keinen eigenen Taper aus und verändern die Tage/Wochen davor nicht. In der Rennwoche ersetzen sie den Longrun; die übrigen Einheiten bleiben in einer normalen konfliktfreien Woche erhalten.
- **Zielzeit-Empfehlung:** unter der Zielzeit jedes Rennens zeigt Laufapp dezent die aktuelle datenbasierte Prognose und den Prognosebereich an. Die Empfehlung kann übernommen werden, bleibt aber eine Nutzerentscheidung.
- **Wissenschaftlich orientierte Marathonengine:** die lokale, LLM-unabhängige Planung trennt Trainingsphase, physiologisches Ziel, Workoutform, Belastung und Recovery. Qualität wird nicht mehr nach einem festen Wochentagsmuster ausgewählt.
- **Workout Variation Engine:** zuerst wird der gewünschte Reiz festgelegt (u. a. Schwelle, VO₂max, Ökonomie, Marathonpace, aerobe Progression, Hügel), danach deterministisch eine passende Form gewählt. Die Historie der Qualitätseinheiten verhindert unnötige identische Wiederholungen in kurzem Abstand.
- **Longrun-Progression:** Easy, Progression, Fast Finish, MP-Blöcke und Deload werden getrennt geplant. Distanz und Intensität werden nicht regelmäßig gleichzeitig stark erhöht. Reale Longrun-Historie kann 30–35-km-Peakläufe ermöglichen, das Nutzermaximum bleibt hart.
- **Qualitätsbudget:** intensive Longruns zählen als Qualitätsreiz. Ist nur eine Qualitätseinheit pro Woche konfiguriert, verbraucht ein MP-/intensiver Longrun dieses Budget; der andere strukturierte Lauf wird dann nur als kleine Ökonomie-/Aktivierungseinheit dosiert statt als zweite harte Schwellen-/VO₂max-Einheit.
- **Aktuelle statt blinde Zielpace:** Goal Marathon Pace und Current Estimated Marathon Pace sind getrennt; Trainingsgeschwindigkeiten folgen primär dem aktuell gestützten Leistungsniveau.
- **Rollierende Intensitätssteuerung:** niedrig/moderat/hoch wird über vier Wochen bewertet. Der Marathonplan bleibt deutlich niedrigintensiv dominiert; Prozentbereiche sind Orientierungen und keine starren Grenzwerte.
- **Readiness + subjektives Feedback:** persönliche HRV-/Ruhepuls-Baseline, Schlaf, RPE, Beine, Schmerzen, Erholung und vorhandene Laufreaktionen werden kombiniert. Ein einzelner HRV-Wert entscheidet nicht allein. Änderungen bleiben bestätigungspflichtige Vorschläge.
- **Warum diese Einheit?:** besondere Qualitätseinheiten und Longruns tragen physiologisches Ziel, Workoutform, geschätzte Belastung und eine kurze Begründung.
- **Blockprogression:** Build-/Specific-Belastungswochen werden nicht mehr jede Woche isoliert aus derselben Basis berechnet. Innerhalb eines Belastungsblocks kann der Umfang deterministisch ansteigen; Recovery, Taper, Detraining und Nutzerlimits bleiben wirksam.
- **Schuh nachträglich zuordnen:** Ein absolvierter, mit einem realen Lauf verknüpfter Wochenplan-Eintrag kann direkt einem Schuh zugeordnet werden. Die Kilometer des realen Laufs fließen sofort in die bestehende Schuhbilanz ein. Die Zuordnung im Fortschritt-Tab bleibt ebenfalls möglich.
- **16-Wochen-Simulation in CI:** ein kompletter Marathonzyklus wird synthetisch geplant, absolviert und Woche für Woche erneut aus der entstandenen Historie berechnet. Geprüft werden Variation, Deload, MP-Longruns, Taper, Belastungsvektor, Intensitätsverteilung, VO₂max-Dosierung und der vollständige Zielmarathon.
- **Neun reproduzierbar randomisierte Läuferprofile in CI:** 3–7 Lauftage, 1–3 Qualitätseinheiten, etwa 25–100 km etablierter Wochenumfang, unterschiedliche Leistungsstände, Nutzerlimits, automatische Limits, ambitionierte Zielzeiten, Detraining und B-Rennen werden über komplette Trainingsblöcke simuliert. Die Tests prüfen u. a. Wochen-/Longrun-Grenzen, Qualitätsbudget, Longrun-Distanz-vs.-Intensität, Zielpace-Cap, Workoutvariation und DB-Integrität. Diese Zusatztests deckten eine reale Lücke beim Qualitätsbudget auf; der Fix ist jetzt Teil der permanenten Regression.
- **Kompatibel zu v0.1.9:** keine neue Datenbankschemaversion; bestehende Rennen werden bei fehlender A/B-Klassifikation als A-Rennen behandelt. Health-Daten, Läufe, Schuhe, manuelle Planänderungen und Ingress-Schutz bleiben erhalten.

Ausführliche Trainingslogik und Evidenzabgrenzung: **`TRAINING_ENGINE.md`**. Insbesondere die alternierende Longrun-Distanz/MP-Strategie und konkrete Workoutrotationen werden dort als konservative evidenzinformierte Designableitungen dokumentiert, nicht als direkt bewiesene überlegene Sequenzen.

> Statisch/isoliert getestet; Home-Assistant-Integration muss auf dem Beelink verifiziert werden. Reale Nabu-Casa-, Beelink- und iPhone-Prüfungen stehen aus.

## Highlights von v0.1.9

- **Plan neu berechnen** funktioniert aus Einstellungen auch dann, wenn die Wochenansicht vorher noch nicht geöffnet wurde; ein fehlender Wochenstart wird sauber als aktuelle Kalenderwoche behandelt.
- Die Planneuberechnung erzeugt keine neue automatische Einheit auf einem Tag, an dem bereits eine absolvierte, verknüpfte oder manuell geschützte Einheit liegt. Von v0.1.8 erzeugte, eindeutig überflüssige Engine-Dubletten auf solchen Tagen werden beim Laden/Neuberechnen der Woche konservativ entfernt.
- Der automatisch neu erzeugte Restplan berücksichtigt den bereits geschützten Wochenumfang. Nutzergrenzen für Wochenkilometer und Longrun bleiben damit echte Obergrenzen für automatisch erzeugte Einheiten, ohne absolvierte/manuelle Einheiten umzuschreiben.
- **Fortschritt:** Wochenbeschriftungen stehen wieder unter den Balken statt über dem Diagramm.
- **Woche:** der Drag-Griff bleibt bewusst nur an geplanten, verschiebbaren Einheiten sichtbar; nicht verschiebbare/absolvierte Zeilen bleiben nun trotzdem exakt gleich ausgerichtet.
- Keine Datenbankschemaänderung; bestehende persistente Daten bleiben erhalten.

## Highlights von v0.1.8

- Eigener Bereich **Einstellungen** für 3–7 Lauftage, Wochentage, 1–3 Qualitätseinheiten sowie harte Wochen- und Longrun-Grenzen.
- Der maximale Wochenumfang arbeitet wahlweise automatisch oder als dauerhaft gespeicherte Nutzergrenze; die automatische Empfehlung ist die robuste Basis abgeschlossener Wochen × 1,10 (Marathon), 1,08 (Halbmarathon) oder 1,06 (kürzere Distanzen), bei erkanntem Detraining zusätzlich × 0,95.
- Distanzabhängige Longrun-Grenzen: Marathon 35 km, Halbmarathon 26 km, 10 km 18 km und 5 km 14 km.
- „Plan neu berechnen“ befindet sich zentral in Einstellungen; Änderungen markieren den Plan zunächst nur als veraltet und schützen absolvierte sowie manuell angepasste Einheiten.
- Die Aktualisierungszusammenfassung vergleicht ausschließlich tatsächliche Planzeilen derselben ausgewählten Kalenderwoche statt mehrerer Zukunftswochen.
- **Aktuelle Woche** bringt die Wochenansicht direkt zum gegenwärtigen Montag zurück.

## Highlights von v0.1.7

- Deterministische adaptive Trainingsengine mit robuster Basis aus abgeschlossenen Wochen.
- Explizite Planfrische und „Plan neu berechnen“ ohne Überschreiben manueller/absolvierter Einheiten.
- Rennrelative Phasen, Recovery, Marathon-Long-Runs und Qualitätsperiodisierung; kompakte Planbasis.
- Details: `TRAINING_ENGINE.md` im Repository.

## Highlights von v0.1.6

- **Apple Health:** klare Diagnose für Zeitraum, ungültige Läufe sowie erkannt/vorhanden/neu; Drag & Drop für Exportdateien und optionaler transaktionssicherer Ersatz ausschließlich der Apple-Daten.
- **Wochenübersicht:** der Drag-Griff tauscht geplante Workout-Karten zuverlässig oder verschiebt auf freie Tage; Wischen und „Verschieben“ bleiben erhalten.
- **Fortschritt:** antippbare Wochenbalken mit dezent rot akzentuiertem Kilometer-Overlay, „Dieses Jahr“/„Letztes Jahr“ und lesbare, sparsame Langzeitbeschriftung.

„Dieses Jahr“ läuft vom 1. Januar bis heute, „Letztes Jahr“ vom 1. Januar bis 31. Dezember des Vorjahres. „12 Monate“ bleibt davon getrennt ein rollierender Zeitraum. Bei Wochen über Silvester werden nur Läufe innerhalb des gewählten Kalenderjahres summiert.

> Die Behebung des konkreten Produktionsimports muss mit dem realen Export auf dem Beelink bestätigt werden. Statisch/isoliert getestet; Home-Assistant-Integration muss auf dem Beelink verifiziert werden.

## Highlights von v0.1.5

- Robuster nativer Apple-Health-Import: Workout-Attribute und verschachtelte `WorkoutStatistics`, aggregierte Diagnose, sichere Reimport-Deduplizierung und Warnung bei verdächtigen Null-Ergebnissen. Recovery-Signale und Prognosen werden nach dem Import beim nächsten Aufruf frisch geladen.
- Wochenübersicht: Wischen im Kalenderkopf wechselt die Woche; geplante Einheiten lassen sich am Griff per Pointer Events verschieben. Freier Tag bedeutet Verschieben, belegter geplanter Tag atomaren Tausch. „Verschieben“ bleibt als zugänglicher Fallback erhalten; abgeschlossene/ausgefallene Einheiten sind geschützt.
- Fortschritt: Wochenkilometer für Monat, 3, 6 oder 12 Monate aus der vollständigen relevanten Laufhistorie statt nur den letzten 100 Läufen; Standard ist 3 Monate.
- Bottom-Navigation: Symbole und Beschriftungen sind rund 18 % größer.

Zeiträume sind rollierende Kalendermonate bis heute; die angebrochene aktuelle Woche wird eingeschlossen. Frühere unbekannte Historie wird nicht erfunden, echte Nullwochen innerhalb des gewählten Bereichs werden gezeigt.

> Die Behebung des konkreten Produktionsimports muss mit dem realen Export auf dem Beelink bestätigt werden. Statisch/isoliert getestet; Home-Assistant-Integration muss auf dem Beelink verifiziert werden.

## Highlights von v0.1.4

- **Große Apple-Health-Uploads über Ingress:** Home Assistant streamt große Apple-Health-Uploads direkt zur Laufapp. Dadurch können auch große Exportdateien zuverlässig über Ingress hochgeladen werden, ohne die bestehende Ingress-only-Zugriffskontrolle zu ändern.

### Weiterhin enthalten aus v0.1.3

- **Persistente Daten über Updates:** Läufe, Health-Metriken, Schuhe, Wettkämpfe, Trainingsplan, Bestleistungen und Coach-Daten bleiben in `/data/laufapp.sqlite3` erhalten.
- **Versionierte Datenbankmigration:** v0.1.2 wird beim Start automatisch auf Schema 2 migriert. Vor jeder Schemaänderung entsteht eine SQLite-Sicherung unter `/data/backups/`; bei einem Migrationsfehler wird der Vorzustand aus dem Backup wiederhergestellt und der App-Start abgebrochen.
- **Apple Health als Hintergrundjob:** Nach abgeschlossenem Upload kann der Browser bzw. die Home-Assistant-App geschlossen oder minimiert werden. Der Beelink verarbeitet die Datei weiter. Status und Ergebnis bleiben abrufbar; ein durch App-Neustart unterbrochener Job wird beim nächsten Start erneut aufgenommen.
- **Detaillierte Laufdaten:** Soweit Apple sie exportiert, werden zeitaufgelöste Herzfrequenz, Running Speed, Running Power, Schrittlänge, vertikale Oszillation, Bodenkontaktzeit, abgeleitete Kadenz sowie GPX-/Höhendaten einem Lauf zugeordnet.
- **GitHub-Umzug vorbereitet:** v0.1.3 enthält einen sicheren Einmal-Transfer von der bisherigen lokalen Home-Assistant-App zur späteren GitHub-Repository-App, ohne erneuten Health-Import.
- **GitHub CI vorbereitet:** Compilecheck, JavaScript-Syntaxcheck, vollständige Regressionstests und Docker-Build laufen künftig bei Push/PR automatisch.

## Bestehende Funktionen

- **Heute:** nächstes A-Rennen als Planfokus, Zielzeit, Prognose, Zielbewertung, nächste Einheit, Recovery-Signale und offene Coach-Vorschläge.
- **Woche:** 3–7 geplante Trainingseinheiten gemäß Einstellungen, Status, Wochenkilometer, RPE + Pace, Verschieben auch in angrenzende Wochen, Planqualitäts- und Longrun-Guardrails; B-Rennen ersetzen in ihrer Rennwoche den Longrun.
- **Trainingssteuerung:** konfigurierbare Lauftage, Qualitätseinheiten, Planungsaggressivität, automatische/manuelle Wochenobergrenze, maximale Longrun-Distanz sowie bestehende Guardrails.
- **Rennen:** mehrere A-/B-Rennen, eigene Zielzeit, Laufapp-Zeitempfehlung und automatische A-Renn-Fokusübergabe.
- **Fortschritt:** Prognosen für 5 km, 10 km, Halbmarathon und Marathon mit Unsicherheitsbereich, Wochenkilometer und Leistungsprofil; absolvierte Läufe können nachträglich einem Schuh zugeordnet werden.
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

Der API-Key verbleibt serverseitig in der Home-Assistant-App-Konfiguration (`/data/options.json`) und wird nie an das Browser-Frontend ausgeliefert. Ohne API-Key funktionieren Plan, Prognosen, Health-Import, Wochenübersicht, Läufe, Schuhe und Rennverwaltung vollständig.

Standardmodelle: `gpt-5.6-terra` für den Coach und `gpt-5.6-luna` für Screenshot-Extraktion. Wissenschaftliche Websuche ist optional.

## Teststatus

Die automatisierte GitHub-CI prüft Python-Compilecheck, JavaScript-Syntax, vollständige Pytest-Regression, die eigenständige 16-Wochen-Marathonsimulation, **neun reproduzierbar randomisierte Läuferprofile**, den Home-Assistant-Docker-Build und einen Docker-Runtime-Smoke-Test. Für v0.2.2 prüft der Runtime-Test zusätzlich die tatsächliche HTTP-Auslieferung der verschachtelten v0.2-Assets sowie die Renn- und Einstellungs-APIs. Der aktuelle v0.2.2-Stand besteht **82/82 Pytests** plus dem vollständigen 16-Wochen-Simulator und dem separaten 9-Profil-Simulator.

Statisch/isoliert getestet; Home-Assistant-Integration muss lokal auf dem Beelink verifiziert werden. Reale iPhone-/Nabu-Casa-Interaktionen sind nicht Bestandteil der isolierten CI.

## Lokale Entwicklung

```bash
cd laufapp/app
export LAUFAPP_DATA_DIR=/tmp/laufapp-data
export LAUFAPP_TRANSFER_DIR=/tmp/laufapp-transfer
export LAUFAPP_TRUSTED_INGRESS_ONLY=0
uvicorn main_v022:app --host 127.0.0.1 --port 8099
```
