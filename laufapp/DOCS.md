# Laufapp v0.1.3 – Bedienung

## Heute
Wettkampfziel, aktuelle Prognose, Zielbewertung, nächste Einheit und Recovery-Signale.

## Woche
Vier geplante Laufeinheiten mit Distanz, Pace, RPE und Status. Einheiten können verschoben bzw. als absolviert/ausgefallen markiert werden. Lokale Guardrails prüfen Longrun-Anteil und belastende Einheiten. Der optionale wissenschaftliche Wochencheck darf nur Vorschläge erzeugen.

## Fortschritt
5-km-, 10-km-, Halbmarathon- und Marathonprognosen, Unsicherheitsbereiche, Wochenkilometer, aktuelle Läufe und Leistungsprofil.

## Coach
Der Coach berücksichtigt Wettkampf, Wochenplan, Prognosen, jüngste Läufe und relevante Health-Trends. Planänderungen müssen immer bestätigt werden.

## Mehr → Apple Health
Ein ZIP- oder XML-Export wird zunächst vollständig auf den Beelink hochgeladen. **Sobald der Upload abgeschlossen ist, darf die App geschlossen oder minimiert werden.** Der serverseitige Hintergrundjob zeigt Phasen und Fortschritt an. Ein unterbrochener Verarbeitungsjob kann nach App-Neustart wieder aufgenommen werden.

Soweit Apple sie exportiert, speichert Laufapp auch zeitaufgelöste Herzfrequenz, Running Speed/Power, Schrittlänge, vertikale Oszillation, Bodenkontaktzeit, Kadenz sowie GPS-/Höhendaten.

## Mehr → App → GitHub-Umzug
Dieser Button ist nur für den einmaligen Wechsel von der bisherigen lokalen Installation zur GitHub-Repository-App gedacht. Er erzeugt eine integrity-geprüfte Datenbankkopie für die neue App. Die alte lokale App erst entfernen, nachdem die Daten in der GitHub-App geprüft wurden.

## OpenAI API-Key
In Home Assistant bei **Laufapp → Konfiguration** eintragen und die App neu starten. Der Key wird nicht an das Browser-Frontend ausgeliefert.
