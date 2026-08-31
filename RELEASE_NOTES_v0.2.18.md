# Laufapp v0.2.18

## Mehrere Rennen ohne rückwirkende Planänderung

v0.2.18 macht aus dem bisherigen A/B-System einen echten Wettkampfkalender mit **A-, B- und C-Prioritäten**. Mehrere A-Rennen dürfen gleichzeitig existieren. Für jede Trainingswoche bestimmt die Engine chronologisch, welches A-Rennen diese Woche steuert: Vor dem ersten A-Rennen hat ein späteres A-Rennen keinen Einfluss auf dessen Aufbau, spezifische Phase oder Taper. Erst die erste Trainingswoche nach dem früheren A-Rennen wechselt auf das nächste A-Ziel.

Nach einem A-Marathon wird die erste Folgewoche als bewusst reduzierte Easy-only-Recovery geplant. Liegt das nächste A-Rennen kurz danach, folgt ein kontrollierter Wiedereinstieg beziehungsweise Taper statt eines unrealistischen neuen Aufbau-Blocks. Bei größeren Abständen kehrt die normale Periodisierung nach der Erholung zurück.

**B-Rennen** bleiben sekundäre Rennen und ersetzen nur den Longrun ihrer Rennwoche. **C-Rennen** dienen als Trainingswettkampf: kurze C-Rennen ersetzen eine Qualitäts-, längere C-Rennen eine lange Einheit. Beide Prioritäten erzeugen keinen eigenen Taper und ändern keine vorherigen Wochen.

## Harte Vergangenheitssperre

Rennkalender- und Planänderungen dürfen nur das aktuelle Datum und die Zukunft verändern. Vollständig vergangene Wochen werden weder bereinigt noch neu erzeugt. In einer angebrochenen aktuellen Woche bleiben alle Termine vor heute unangetastet. Auch ein API-/UI-Refresh mit einem absichtlich alten Startdatum kann diese Grenze nicht umgehen.

Bereits erzeugte zukünftige Wochen werden bei Änderungen an A-Rennen automatisch neu auf den Kalender ausgerichtet. Noch nicht materialisierte Wochen bleiben lazy und wählen beim ersten Öffnen das dann korrekte nächste A-Rennen.

## Race-Week-Korrektur

Im Zuge der neuen Regressionstests wurde ein bestehender Fehler entdeckt und behoben: A-Rennen unter Marathon-Distanz konnten in der Rennwoche bisher durch den normalen Longrun-Zweig laufen. Ab v0.2.18 werden 5-km-, 10-km-, Halbmarathon- und Marathon-A-Rennen als echte Wettkampfeinheit am tatsächlichen Renndatum mit vollständiger Distanz erzeugt.

Keine Datenbankschemamigration. Health Auto Export, Nabu-Casa-/Home-Assistant-Relay, Aktivitätsverknüpfung und Security-Grenzen bleiben unverändert.
