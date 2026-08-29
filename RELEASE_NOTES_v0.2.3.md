# Laufapp v0.2.3

## Sehr aggressive Planungsstufe

Die Planungsaggressivität erhält eine vierte Stufe **Sehr aggressiv**.

- Konservativ: bestehendes `gradual`-Profil.
- Moderat: bestehendes `steady`-Profil und Standard.
- Aggressiv: bestehendes `progressive`-Profil.
- Sehr aggressiv: basiert vollständig auf `progressive` und erhöht das daraus berechnete Wochenziel in normalen Belastungswochen anschließend um **2,5 %**.

Die 2,5 % sind bewusst ein zusätzlicher Planungsparameter und keine als wissenschaftlich bewiesen dargestellte Trainingsregel. Recovery-, Taper- und Rennwochen werden nicht angehoben. Nutzergrenzen für Wochenumfang und Longrun, Readiness, Qualitätsbudget sowie die übrigen bestehenden Guardrails bleiben bindend.

Zur Rückwärtskompatibilität bleibt der persistierte Basiswert `training_volume_profile` in diesem Modus `progressive`; der zusätzliche Boost wird separat gespeichert. Ältere Codepfade sehen deshalb weiterhin einen gültigen bekannten Profilwert.

## Regression

Neue Tests prüfen:

- ungefähr +2,5 % Wochenziel gegenüber **Aggressiv** in einer normalen Build-Belastungswoche,
- keine zusätzliche Anhebung im Taper,
- weiterhin bindende Nutzerobergrenzen,
- persistente API-Umschaltung zwischen allen vier Stufen,
- Auslieferung und Syntax der neuen mobilen UI.

Keine Datenbankschemamigration.
