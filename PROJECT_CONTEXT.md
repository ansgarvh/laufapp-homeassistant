# Projektkontext

Laufapp v0.1.7 ist eine Home-Assistant-Ingress-App mit lokaler SQLite-Persistenz. Die Baseline-Trainingsplanung ist vollständig lokal, reproduzierbar und ohne LLM nutzbar; der optionale Coach darf Änderungen nur nach Annahme anwenden.

Die Trainingsengine nutzt ab v0.1.7 robuste abgeschlossene Wochen, rennrelative Trainingsphasen, Long-Run-Historie und eine explizite Planfrische. Health-Importe ändern bestehende Pläne nie still. Details und Altursache stehen in [TRAINING_ENGINE.md](TRAINING_ENGINE.md).
