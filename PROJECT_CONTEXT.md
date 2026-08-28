# Projektkontext

Laufapp v0.1.8 ist eine Home-Assistant-Ingress-App mit lokaler SQLite-Persistenz. Die Baseline-Trainingsplanung ist vollständig lokal, reproduzierbar und ohne LLM nutzbar; der optionale Coach darf Änderungen nur nach Annahme anwenden.

Die Trainingsengine nutzt ab v0.1.7 robuste abgeschlossene Wochen, rennrelative Trainingsphasen, Long-Run-Historie und eine explizite Planfrische. Health-Importe ändern bestehende Pläne nie still. Details und Altursache stehen in [TRAINING_ENGINE.md](TRAINING_ENGINE.md).


## v0.1.8
Planungslimits liegen als additive Schlüssel in der bestehenden Settings-Tabelle. Der automatische Wochen-Maximalwert verwendet ausschließlich robuste abgeschlossene Wochen (Distanzfaktor 1,10/1,08/1,06; bei echtem Detraining × 0,95). Eine Nutzergrenze bleibt unverändert, bis ausdrücklich zu Automatisch gewechselt wird. Die Refresh-Differenz bezieht sich auf genau `summary_week_start`.
