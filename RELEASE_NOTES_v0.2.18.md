# Laufapp v0.2.18

## Schwerpunkt

v0.2.18 macht den Wettkampfkalender zu einem echten Mehrziel-System und verbessert die Rennanlage. Ein späteres A-Rennen darf die Vorbereitung auf ein früheres A-Rennen nicht verändern. Nach dem ersten A-Rennen wechselt die Engine auf das nächste A-Ziel, berücksichtigt aber zuerst die notwendige Erholung.

## Wettkampfprioritäten

- **A-Rennen:** steuert Periodisierung, spezifischen Block, Peak, Taper und Rennwoche. Bei mehreren A-Rennen ist bis zum jeweiligen Rennen immer das chronologisch nächste A-Ziel maßgeblich.
- **B-Rennen:** ersetzt nur den Longrun seiner Rennwoche. Die vorherigen Wochen werden nicht für das B-Rennen getapert.
- **C-Rennen:** kontrollierter Trainingswettkampf; ersetzt eine Qualitätseinheit, ersatzweise einen Easy Run. Longrun und A-Rennen-Periodisierung bleiben bestehen.

## Übergang zwischen A-Rennen

Für nahe aufeinanderfolgende A-Rennen wird nicht unmittelbar nach Rennen 1 ein normaler Aufbau für Rennen 2 gestartet. Die erste vollständige Woche nach dem A-Rennen wird als Recovery behandelt. Liegt das nächste A-Rennen bereits sehr nahe, folgt danach eine kurze Taper-/Aktivierungsphase. Dadurch bleibt z. B. ein Marathon vollständig bis zu seinem Termin planbestimmend; ein 19 Tage späterer Halbmarathon beeinflusst erst die Zeit nach dem Marathon.

## Rennwoche für 5 km bis Marathon

Ein bestehender Fehler im Longrun-Planer wurde behoben: A-Rennen unter 40 km konnten in ihrer Rennwoche fälschlich als normaler Longrun behandelt werden. A-Rennen über 5 km, 10 km, Halbmarathon und Marathon werden jetzt als exakter Zielwettkampf am gespeicherten Datum und mit der vollständigen Wettkampfdistanz erzeugt.

## Rennanlage

Die Eingabemaske enthält jetzt getrennt:

- Wettkampfart: 5 km, 10 km, Halbmarathon oder Marathon
- exakte Distanz in km
- Priorität: A, B oder C
- Datum und Zielzeit

Die Wettkampfart belegt die übliche Standarddistanz vor. Das Distanzfeld bleibt editierbar und akzeptiert deutsches Dezimalkomma ebenso wie den Punkt, beispielsweise `21,0975` und `21.0975`.

## Kompatibilität

Keine Datenbankschemamigration. Bestehende Rennen ohne gespeicherte Wettkampfart werden anhand ihrer Distanz einer Standardart zugeordnet. Die vorhandene A/B-Prioritätsablage bleibt kompatibel und wurde um C erweitert. Health Auto Export, Nabu-Casa-Relay, Ingress-Security, Aktivitätsverknüpfung und Leistungsprofil bleiben unverändert.

## Tests

Neue Tests decken insbesondere ab:

- zwei A-Rennen mit 19 Tagen Abstand,
- unveränderte Planung vor dem ersten A-Rennen,
- Recovery- und Taper-Handover zum zweiten A-Rennen,
- korrekte A-Halbmarathon-Rennwoche,
- C-Rennen als Ersatz für Qualität bei erhaltenem Longrun,
- API-Roundtrip von Wettkampfart und C-Priorität,
- deutsches Dezimalkomma und Wettkampfart-Dropdown.

Zusätzlich bleiben die vollständige Regression, Simulationen, Security-Gates und Docker-/HAE-/Nabu-/Ingress-E2E verpflichtend.
