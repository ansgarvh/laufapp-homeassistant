# Laufapp – Leistungsprofil v0.2.17

Das Leistungsprofil ist eine **transparente, evidenzinformierte Trainingsheuristik auf einer Skala von 0 bis 100**. Es ist kein physiologisches Maximum, kein Perzentil und kein Ersatz für eine Leistungsdiagnostik. Der Score beschreibt, wie gut die aktuell vorliegenden Trainingsdaten die für das aktive Wettkampfziel relevanten Merkmale abdecken.

## Ausdauerbasis

Aus acht **abgeschlossenen** Kalenderwochen werden durchschnittlicher Wochenumfang und Zeit auf den Beinen bewertet. Die Distanzreferenz ist zielabhängig (5 km 30 km/Woche, 10 km 35 km/Woche, Halbmarathon 45 km/Woche, Marathon 55 km/Woche) und kann durch eine höhere konfigurierte persönliche Basis moderat angehoben werden. Liegen in beiden Vier-Wochen-Hälften mindestens zwei mit einem Easy-Workout verknüpfte Läufe mit plausibler Durchschnittsherzfrequenz vor, wird die Entwicklung von Geschwindigkeit pro Herzschlag nur als kleiner Bonus/Malus (maximal ±8 Punkte) berücksichtigt. Dadurch dominieren Hitze, Höhenprofil oder Messfehler nicht den Score.

## Speed-Ausdauer

Der Kern ist der 5-km→10-km-Leistungserhalt relativ zur bereits in Laufapp verwendeten Riegel-Hochrechnung. Ein zusätzlicher Abfall gegenüber dieser Referenz reduziert den Score. Wenn genügend vergangene Quality-/Race-Prep-Planreize existieren, fließt deren tatsächliche Erfüllung mit 20 % ein. Der Wert bewertet daher **nicht die absolute Sprint- oder 5-km-Geschwindigkeit**.

## Schwellen-Ausdauer

Analog wird der 10-km→Halbmarathon-Leistungserhalt betrachtet. Genügend vorhandene Quality-/Race-Prep-Einheiten fließen mit 20 % ein; ein vorhandener Easy-Pace/HF-Trend darf den Wert nur geringfügig verändern. Der Score ist ausdrücklich **keine gemessene Laktat- oder ventilatorische Schwelle**.

## Zielspezifische Readiness

Die Bezeichnung passt sich dem aktiven Ziel an (z. B. Marathon-Readiness oder Halbmarathon-Readiness). Eingerechnet werden Wochenumfang, längster Lauf der letzten acht Wochen, Wiederholung ausreichend langer Läufe und – wenn genügend Planhistorie vorhanden ist – die Erfüllung von Longrun-, Quality- und Race-Prep-Einheiten. Die Longrun-Referenzen liegen bei 10 km (5-km-Ziel), 14 km (10-km-Ziel), 20 km (Halbmarathon) und 30 km (Marathon).

## Trainingskontinuität

Bewertet werden aktive Wochen, die durchschnittliche Laufhäufigkeit relativ zu den konfigurierten Lauftagen und – bei ausreichend Planhistorie – der Anteil tatsächlich absolvierter vergangener Planeinheiten. Dadurch ist der Wert aussagekräftiger als die frühere feste Regel „Woche ≥12 km“.

## Health-Kontext

Ruhepuls, HRV, Schlaf und VO₂max aus den letzten 28 Tagen werden separat angezeigt, **aber nicht direkt in einen universellen Fitnessscore umgerechnet**. Absolute Werte sind stark individuell und hängen unter anderem von Messgerät, Tageszeit, Belastung, Schlaf und Umweltbedingungen ab.

## Wissenschaftlicher Rahmen

Die Auswahl der Dimensionen orientiert sich an denselben Prinzipien wie die Trainingsengine: Trainingsumfang, überwiegend niedrigintensive Belastung, Longrun-Historie, zielspezifische Einheiten und Trainingskontinuität. Die exakten 0–100-Gewichte sind bewusst als transparente Produktheuristik dokumentiert und nicht als wissenschaftlich validierter Index dargestellt. Siehe auch `TRAINING_ENGINE.md` und die dort aufgeführten Quellen, insbesondere die Arbeiten zu Trainingsumfang/Intensitätsverteilung sowie zum Zusammenhang von Trainingsvolumen und längstem Ausdauerlauf mit (Halb-)Marathonleistung.
