# Deterministische Trainingsengine (v0.1.7)

## Verifiziertes Altverhalten und Ursache

v0.1.6 gab in `generate_week()` eine persistierte native Woche unverändert zurück. Health-Importe ergänzten Läufe und aktualisierten Prognosen, regenerierten aber keine Workouts und markierten sie nicht als veraltet. Einstellungen regenerierten die aktuelle Woche teilweise sofort. Zudem mittelte `_weekly_target()` vier Wochen einschließlich der unvollständigen laufenden Woche. So konnten 60–70-km-Wochen plus eine partielle Woche die Basis deutlich absenken; ein vor dem Import erzeugter Plan blieb zusätzlich auf der Defaultbasis. `_templates()` begrenzte den Long Run auf rund 38 % des Wochenziels (und maximal 32 km), wodurch aus etwa 55 km rund 21 km entstanden.

## Algorithmus

Die lokale Engine ist ohne LLM deterministisch. Sie verwendet acht abgeschlossene Kalenderwochen. Wochen unter 5 km gelten im robusten Schätzer als inaktiv; bei mindestens fünf aktiven Wochen werden höchster und niedrigster Wert entfernt, sonst wird der Mittelwert aktiver Wochen verwendet. Die laufende Teilwoche wird nur als Kontext ausgewiesen. Drei streng fallende abgeschlossene Wochen, deren jüngste unter 70 % des robusten Niveaus liegt, aktivieren Detraining: 65 % Mittel der letzten drei plus 35 % robuste Historie. Bei weniger als drei aktiven Wochen gilt `baseline_weekly_km` als Fallback.

Phasen sind aus Wochen bis zum Rennen abgeleitet: Build (>12), marathon-spezifisch (6–12), Peak (3–5), Taper (1–2), Race (0). Recovery folgt einer rennrelativen 4-Wochen-Sequenz im Build bzw. 3-Wochen-Sequenz im spezifischen Block – niemals der ISO-Wochennummer. Progressionsprofile sind kleine Aggressivitätsfaktoren statt unbegrenztem Compound-Wachstum; etablierter Umfang darf das Standard-Sicherheitsdach anheben.

Der Marathon-Long-Run verwendet die längsten Läufe über vier/acht Wochen und Häufigkeiten ab 20/24/28/30 km. Steigerungen sind grundsätzlich auf den letzten Long Run plus 3 km und das Nutzermaximum begrenzt. 30–35 km sind nur in der Peakphase bei mindestens etwa 58 km etablierter Wochenlast, zwei jüngsten 28-km-Läufen und einem Nutzerlimit ab 30 km möglich. Normale Long-Run-Anteile bleiben Stress-Guardrail, nicht starres Erzeugungslimit. Recovery und Taper reduzieren den Lauf. Marathonpace-Finish/-Blöcke zählen als harte Einheit und verkürzen die eigenständige Qualitätseinheit. Qualität rotiert rennrelativ zwischen Schwellenintervallen, Cruise-Intervallen, kontinuierlichem Tempo und Marathonpace.

## Planfrische und Sicherheit

Bedeutende Health-Importe, aktive Wettkampf-/Zieländerungen und planrelevante Einstellungen markieren zukünftige Pläne als veraltet, überschreiben sie aber nicht. Nur die ausdrückliche Aktion **Plan neu berechnen** ersetzt zukünftige, geplante, unverknüpfte Engine-Workouts. Vergangene, absolvierte, ausgefallene, verschobene/getauschte, Coach- oder manuell veränderte Einheiten bleiben erhalten. Vier Wochen werden in einer SQLite-Transaktion aktualisiert; bei Fehler rollt der Request vollständig zurück.

Schema 4 ergänzt additiv `manual_override`, `modified_by`, `generation_version` und `plan_generation_id`. Jede Migration wird wie bisher erst nach einem integritätsgeprüften Online-Backup ausgeführt.

## Evidenzprinzipien

Die Regeln übersetzen keine Einzelstudie in eine scheinpräzise Distanz. Grundlage sind überwiegend lockere Intensitätsverteilung, behutsame Belastungsprogression, spezifische aber dosierte Wettkampfbelastung und ein volumenreduzierter Taper mit etwas erhaltener Intensität. Herangezogen wurden insbesondere Bosquet et al., *Effects of tapering on performance* (Medicine & Science in Sports & Exercise, DOI 10.1249/mss.0b013e31806010e0), Seiler, *What is best practice for training intensity and duration distribution in endurance athletes?* (International Journal of Sports Physiology and Performance, DOI 10.1123/ijspp.5.3.276), sowie ACSM, *Progression Models in Resistance Training for Healthy Adults* als allgemeines Progressions-/Erholungsprinzip (keine marathon-spezifische Distanzvorgabe). Long-Run-Kategorien und 30–35-km-Band sind konservative, practitioner-informed Regeln; die Evidenz stützt keine universell exakte Maximaldistanz.
