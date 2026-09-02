# Laufapp v0.2.27 – explizite Trainingsphasen

v0.2.27 macht den geplanten Ablauf einer Einheit konkret sichtbar. Bei mehrphasigen Qualitätseinheiten steht die schnelle Pace nicht länger ohne Kontext neben der Gesamtdistanz, sondern ist eindeutig dem Hauptteil zugeordnet. Ein- und Auslaufen sowie Erholung werden mit eigenem Ziel dargestellt.

## Strukturierter Ablauf

- Qualitätseinheiten enthalten **Einlaufen**, **Hauptteil**, optional **Erholung** und **Auslaufen**.
- Jeder Abschnitt liefert eine stabile Reihenfolge, Typ, Bezeichnung, Distanz oder Dauer, Wiederholungsparameter, Pace und Ausführungsanweisung.
- Die bekannten Planvarianten für Schwelle, VO₂max, Laufökonomie, Hügel, Fartlek, Progression und Marathonpace werden variantenspezifisch aufgelöst.
- Marathonpace-Longruns trennen lockeren Einstieg, MP-Blöcke, lockere Zwischenabschnitte und Auslaufen. Progressive Longruns weisen den lockeren Hauptteil und den kontrollierten Schluss separat aus.
- Bei zeitbasierten Trab- oder Gehpausen bleibt die geplante Einheitendistanz die Summe aus Einlaufen, Hauptteil und Auslaufen. Die Oberfläche erklärt, dass die tatsächlich aufgezeichnete Distanz durch die Pausen höher sein kann.

## Oberfläche und Pace-Kontext

Der komplette Ablauf ist direkt unter **Heute → Nächste Einheit** sichtbar. In der Wochenübersicht fasst jede Einheit ihre Phasen kompakt zusammen; ein Klick auf eine geplante oder ausgefallene Karte öffnet die vollständige Detailansicht. Die bisherige Pace-Kachel heißt bei mehrphasigen Einheiten **Hauptteil**. Für Ein- und Auslaufen gilt ausdrücklich lockeres RPE 2–3 vor Pace.

## Daten- und HAE-Kompatibilität

Die Phase-Daten werden an der bestehenden Workout-API rückwärtskompatibel ergänzt. Persistierte Workout-Zeilen und das Datenbankschema werden nicht verändert. Damit bleiben bestehende geplante, verschobene, absolvierte, ausgefallene und verknüpfte Einheiten erhalten.

Zusätzlich bewahrt v0.2.27 historische einheitenlose Schlafwerte als Stunden und validiert explizit angegebene Einheiten für VO₂max und Ruhepuls. Unbekannte Einheiten werden nicht als kanonische Einheit umetikettiert.

`custom_components/laufapp_hae_relay` bleibt auf seiner unabhängigen Version `0.2.19`, weil der Transport nicht geändert wird.

## Verifikation

Die Release-Gates prüfen die strukturierten Phasen über direkte Modultests und die Dashboard-/Wochen-API, einschließlich Distanzsummen, Wiederholungen, zeitbasierter Erholung, spezifischer Longruns, Altbeständen und ausbleibender Datenbankmigration. Dazu kommen die vollständige Regression, Syntax-, Trainingssimulations-, Dependency-, Security-, Docker- und E2E-Gates.

Statisch/isoliert und in Linux/Docker getestet. Die echte Home-Assistant-OS-/Ingress-/Custom-Integration-/Nabu-Casa-/Health-Auto-Export-iPhone-Integration muss nach Installation auf dem Zielsystem lokal verifiziert werden.
