# Laufapp v0.2.5

## Fortschritt / Bestzeiten

- Manuell eingetragene und gespeicherte Bestzeiten werden im Fortschritt-Tab sichtbar angezeigt.
- Eine kompakte Bestzeiten-Karte zeigt Distanz, Zeit, Datum und Quelle; alle gespeicherten Bestzeiten können aufgeklappt werden.
- Der Fortschritt-Header erhält einen direkten Bestzeiten-Sprung.
- Prognosekarten zeigen eine positive Entwicklung gegenüber der bestätigten Bestzeit als Zeitdifferenz an.
- Für den Halbmarathon wird die verwendete Bestzeit als Prognosebasis transparent erklärt.

## Prognose nach einer Bestzeit

- Die bestätigte Bestzeit bleibt der harte Leistungsanker.
- Wenn die Punktprognose bisher praktisch an dieser Bestzeit festhing, darf kontinuierliches Training seitdem nun einen begrenzten Entwicklungseffekt liefern.
- Der Entwicklungseffekt benötigt mindestens acht Wochen Abstand zur Bestzeit und mindestens 75 % aktive Trainingswochen im aktuellen Acht-Wochen-Fenster.
- Aktueller Wochenumfang wird mit den acht Wochen vor der Bestzeit verglichen; gestiegener Umfang und eine verbesserte Longrun-Basis können den Entwicklungseffekt verstärken.
- Der reine Trainingsentwicklungs-Effekt ist auf maximal 2,5 % begrenzt und wird nicht auf Marathonprognosen angewendet. Schnellere direkte Leistungsdaten aus v0.2.4 bleiben weiterhin vorrangig.
- Zeitablauf allein erzeugt keine schnellere Prognose.

## Mobile Navigation

- Die untere Navigation nutzt auf iPhones deutlich weniger ungenutzte Safe-Area-Höhe.
- Der freie Bereich unter den Icons/Beschriftungen wird ungefähr halbiert, ohne den Home-Indikator vollständig zu überdecken.
- Composer, Toasts und Seiten-Padding werden an die kompaktere Navigation angepasst.

## Kompatibilität

- Keine Datenbankschemamigration.
- Apple-Health-Import, vorhandene Bestzeiten, Läufe, GPS-/Zeitreihendaten, Rennen, Schuhe, Trainingsplan und Coach-Daten bleiben erhalten.
- Home-Assistant-Ingress und Hintergrundjobs bleiben unverändert.

## Verifikation

- Neue Regressionstests prüfen konsistentes Training nach einer Bestzeit, fehlende Verbesserung bei inkonsistentem Training und die 2,5-%-Obergrenze.
- CI prüft zusätzlich die neuen v0.2.5-Frontend-Assets und den Bestzeiten-Endpunkt im gestarteten Docker-Container.
