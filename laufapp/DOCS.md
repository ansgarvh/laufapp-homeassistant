# Laufapp v0.2.23 – Bedienung

## Heute
Wettkampfziel, aktuelle Prognose, Zielbewertung, nächste Einheit und Recovery-Signale.

## Woche
Vier geplante Laufeinheiten mit Distanz, Pace, RPE und Status. Einheiten können verschoben bzw. als absolviert/ausgefallen markiert werden. Lokale Guardrails prüfen Longrun-Anteil und belastende Einheiten. Der optionale wissenschaftliche Wochencheck darf nur Vorschläge erzeugen.

## Fortschritt
5-km-, 10-km-, Halbmarathon- und Marathonprognosen, Unsicherheitsbereiche, Wochenkilometer, aktuelle Läufe und Leistungsprofil.

## Coach
Der Coach berücksichtigt Wettkampf, Wochenplan, Prognosen, jüngste Läufe und relevante Health-Trends. Die letzten lokalen Chatnachrichten werden als begrenzter Gesprächskontext verwendet. Planänderungen müssen immer bestätigt werden.

## KI-Feedback zu einem Lauf
Unter **Fortschritt** einen Lauf öffnen und **Mit KI analysieren** wählen. Angezeigt werden Soll–Ist, Pace/Verlauf, Herzfrequenz, Laufdynamik, Recovery, nächster Schritt und Datenqualität. Die Analyse wird lokal gespeichert. Nach einer Änderung an RPE, Schuh oder Notiz wird sie als veraltet gekennzeichnet; erst **Erneut analysieren** verursacht einen neuen API-Aufruf.

Übertragen werden nur die Kennwerte des gewählten Laufs, seine verknüpfte Planeinheit, kompakte Vergleichsläufe, Wochenlast und relevante Recovery-Aggregate. GPS-Rohkoordinaten und die vollständige Health-Datenbank werden nicht gesendet.

## Mehr → Apple Health
Ein ZIP- oder XML-Export wird zunächst vollständig auf den Beelink hochgeladen. **Sobald der Upload abgeschlossen ist, darf die App geschlossen oder minimiert werden.** Der serverseitige Hintergrundjob zeigt Phasen und Fortschritt an. Ein unterbrochener Verarbeitungsjob kann nach App-Neustart wieder aufgenommen werden.

Soweit Apple sie exportiert, speichert Laufapp auch zeitaufgelöste Herzfrequenz, Running Speed/Power, Schrittlänge, vertikale Oszillation, Bodenkontaktzeit, Kadenz sowie GPS-/Höhendaten.

## Mehr → App → GitHub-Umzug
Dieser Button ist nur für den einmaligen Wechsel von der bisherigen lokalen Installation zur GitHub-Repository-App gedacht. Er erzeugt eine integrity-geprüfte Datenbankkopie für die neue App. Die alte lokale App erst entfernen, nachdem die Daten in der GitHub-App geprüft wurden.

## OpenAI API-Key
In Home Assistant bei **Laufapp → Konfiguration** eintragen und die App neu starten. Der Key wird nicht an das Browser-Frontend ausgeliefert. Ohne Key bleiben Trainingsplan, Prognosen, Importe, Läufe und alle lokalen Auswertungen vollständig nutzbar. OpenAI-Response-Speicherung ist mit `store=false` deaktiviert; die allgemeinen Datenkontrollen und Abuse-Monitoring-Regeln des eigenen OpenAI-Projekts gelten weiterhin.
