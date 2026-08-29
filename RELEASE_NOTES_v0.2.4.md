# Laufapp v0.2.4

## Bestzeiten und Leistungsanker

- Die bereits vorhandene manuelle Bestleistungsfunktion (Distanz, Zeit, Datum) wird jetzt als harter Leistungsanker in der Prognose ausgewertet.
- Apple-Health-Läufe der letzten 24 Monate werden auf Bestleistungen über 5 km, 10 km, Halbmarathon und Marathon geprüft.
- Automatische Erkennung akzeptiert nur Läufe nahe der jeweiligen Standarddistanz; längere Läufe werden nicht als ungemessene Zwischenzeit interpretiert.
- Automatisch erkannte Apple-Health-Bestwerte werden getrennt von manuellen/Wettkampf-Bestzeiten gespeichert und überschreiben niemals Nutzereingaben.
- Bestehende Installationen profitieren sofort aus den bereits importierten Läufen; ein erneuter Apple-Health-Import ist für die Prognose nicht erforderlich.
- Neue Apple-Health-Importe synchronisieren die automatisch erkannten Leistungsanker dauerhaft.

## Prognose

- Leistungsmarken werden über den vollständigen 24-Monats-Zeitraum berücksichtigt statt nur ungefähr 18 Monate.
- Eine bestätigte Bestzeit bleibt die belastbare Leistungsbasis.
- Schnellere aktuelle Trainingsleistungen dürfen eine Verbesserung gegenüber der Bestzeit anzeigen, werden wegen ihrer geringeren Aussagekraft aber konservativ mit dem bestätigten Leistungsanker kombiniert.
- Die Prognose liefert intern zusätzlich den verwendeten Performance-Anker und die geschätzte Verbesserung seit diesem Anker.

## Kompatibilität

- Keine Datenbankschemamigration erforderlich.
- Bestehende Läufe, Apple-Health-Zeitreihen, GPS-Daten, Schuhe, Rennen, Trainingspläne, manuelle Änderungen und Coach-Daten bleiben unverändert.
- Home-Assistant-Ingress und die bestehende Hintergrundjob-Pipeline bleiben erhalten.

## Validierung

- Neue Regressionstests decken 24-Monats-Grenze, Halbmarathon-Erkennung, Schutz manueller Bestzeiten und die Kombination aus alter PB plus aktueller schnellerer Trainingsleistung ab.
- Home-Assistant-/Nabu-Casa-/iPhone-Integration ist nach Installation weiterhin lokal zu verifizieren.
