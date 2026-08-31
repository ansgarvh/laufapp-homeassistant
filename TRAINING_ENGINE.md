# Deterministische Trainingsengine (v0.2.0)

## Zielbild

Die lokale Laufapp-Engine erzeugt den Basistrainingsplan **ohne LLM, ohne Zufall und reproduzierbar**. Die KI ist eine zusätzliche Review-/Erklärungsschicht und darf Planänderungen weiterhin nur als Vorschlag erzeugen. Nutzerentscheidungen, absolvierte Einheiten, verknüpfte Läufe und manuelle Verschiebungen bleiben autoritativ.

v0.2 erweitert die bisherige robuste v0.1.7–v0.1.9-Logik um eine physiologisch orientierte, periodisierte Marathonplanung. Der Algorithmus entscheidet nicht nach dem Muster „Donnerstag = Intervalle“, sondern in dieser Reihenfolge: A-Rennen und Phase → aktuelle Fitness/Trainingsbasis → Recovery → Wochenlastbudget → Longrun-Typ → verbleibendes Qualitätsbudget → physiologisches Ziel → geeignete Workoutform → Dosis → Erklärung.

## Trainingsphasen

Die Engine unterscheidet `foundation`, `build`, `specific`, `recovery`, `taper` und `race`. Die Position entsteht rennrelativ; Recovery hängt vom Trainingsblock ab und nicht von der ISO-Kalenderwoche. Bei mehreren A-Rennen steuert bis zum jeweiligen Renndatum immer das chronologisch nächste A-Rennen. Ein späteres A-Rennen verändert keine davorliegenden Wochen. Nach einem A-Rennen wird bei engem Abstand zum nächsten A-Ziel zunächst Recovery und anschließend eine kurze Übergangs-/Taperphase eingeplant. Ein B-Rennen erzeugt keinen eigenen Taper und ersetzt nur den Longrun seiner Rennwoche. Ein C-Rennen ersetzt nur eine Qualitätseinheit (ersatzweise Easy) und lässt Longrun sowie A-Periodisierung bestehen.

`Foundation` priorisiert lockeres Volumen, Belastbarkeit, Hügel/Ökonomie und moderate Schwellenarbeit. `Build` erhöht Longrun-/Wochenbelastung kontrolliert und enthält gelegentlich VO₂max. `Specific` verschiebt den Schwerpunkt in Richtung Marathonpace, längere Schwellenarbeit und Ermüdungsresistenz; VO₂max tritt zurück. `Taper` reduziert das Volumen deutlich, erhält aber kurze kontrollierte Intensitätsreize und möglichst die Trainingsfrequenz. Die eingegebene Wettkampfdistanz ist in der Rennwoche unveränderlich; ein Marathon wird nicht auf ein Taper-Kilometerziel heruntergerechnet.

## Trainingsbasis und Wochenumfang

Die robuste etablierte Wochenlast aus v0.1.7 bleibt erhalten: abgeschlossenes Training hat Vorrang vor einer unvollständigen laufenden Woche, echter mehrwöchiger Rückgang wird separat erkannt und `baseline_weekly_km` bleibt nur Fallback bei unzureichender Historie. Die Wochenprogression ist block- und phasenabhängig und verwendet **keine starre 10-%-Regel**. Nutzerlimits für den Wochenumfang bleiben harte Obergrenzen; ein höheres Limit ist ein Ceiling und kein Ziel.

Ein normaler vier-Tage-Marathonblock orientiert sich an Easy / Quality / Easy / Longrun. Bei mehr Lauftagen wird zusätzliches Volumen überwiegend locker verteilt. Die konfigurierten Qualitätseinheiten sind ein Belastungsbudget; ein intensiver Marathon-Longrun zählt selbst als Qualitätsreiz und reduziert deshalb die eigenständige Qualitätseinheit.

### Qualitätsbudget bei intensiven Longruns

Die zusätzliche randomisierte Regression hat eine Lücke aufgedeckt: Bei `Qualitätseinheiten = 1` konnte neben einem MP-/Fast-Finish-Longrun noch eine substantielle Schwellen-Einheit entstehen. Damit enthielt die Woche faktisch zwei harte Reize, obwohl nur einer konfiguriert war. Der Fix behandelt den intensiven Longrun nun als den einzigen bedeutenden Qualitätsreiz. Der andere strukturierte Tag wird dann lediglich als kurze Ökonomie-/Aktivierungseinheit dosiert und darf nicht als zweite harte Schwellen-/VO₂max-Einheit auftreten. Dieser Fall ist dauerhaft in der randomisierten CI-Regression abgesichert.

## Intensitätsverteilung

Für Marathontraining wird eine pyramidenförmige Verteilung angestrebt. Die Engine bewertet nicht eine einzelne Woche als starre Prozentvorgabe, sondern projiziert die Belastung rollierend über vier Wochen. `TrainingLoad` enthält dafür geschätzte Minuten niedrig/moderat/hoch sowie Zeit oberhalb LT1, um LT2, oberhalb LT2, Marathonpace-Minuten, Dauer, Distanz, Longrun-Dauer, Höhenmeter (wenn vorhanden), RPE und einen internen Belastungsscore.

Die in der Produktlogik verwendete Orientierung ist: überwiegend niedrigintensiv und normalerweise mindestens ungefähr 70 % niedrigintensive Belastung über den rollierenden Zeitraum. 75–85 % niedrig, 10–20 % moderat und 3–8 % hoch sind **Orientierungsbereiche, keine harten Grenzen**. Bei nur vier Lauftagen darf eine einzelne Woche stärker schwanken.

## Physiologisches Ziel vor Workoutform

Qualitätseinheiten sind in physiologische Ziele getrennt:

- Schwelle / LT2
- VO₂max
- Laufökonomie / Geschwindigkeit
- Marathon-spezifische Ausdauer
- aerobe Progression
- Hügel / Kraftausdauer

Erst nachdem das Ziel feststeht, wählt `WorkoutVariationEngine` deterministisch eine passende Form. Hinterlegt sind unter anderem 4 × 2 km, 3 × 3 km, 2 × 4 km, 3 × 10 min, 2 × 15–20 min, Tempodauerlauf, Cruise Intervals, Progressionsformen, 5 × 1000 m, 6 × 800 m, 4–5 × 1200 m, 10 × 400 m, Bergintervalle, Fartlek und zeit-/distanzbasierte Pyramiden.

Pyramiden sind damit **keine eigene physiologische Kategorie**. Ihre Intensität/Pausen richten sich nach dem ausgewählten Ziel.

### Variation without randomness

Die Variantenauswahl ist reproduzierbar. Zusätzlich wird seit der finalen v0.2-Regression die Historie **nur der Qualitätseinheiten** separat betrachtet. Eine identische Workoutvariante erhält innerhalb von ungefähr drei Wochen eine sehr starke und innerhalb von ungefähr fünf Wochen eine deutliche Wiederholungsstrafe. Das physiologische Ziel bleibt dabei unverändert; die Engine wechselt nur zwischen dafür geeigneten Formen. Falls es für ein Ziel keine gleichwertige Alternative gibt, ist eine Wiederholung weiterhin möglich statt willkürlich ein anderes Energiesystem zu trainieren.

Der 16-Wochen-Regressionstest verlangt mindestens fünf unterschiedliche Qualitätstitel und verhindert unnötige identische Wiederholungen in kurzem Abstand.

## Marathon-Longrun

Der Longrun ist ein eigener Planer mit den Formen Easy, Progression, Fast Finish, Marathonpace-Blöcke und Deload/Reduktion. Verwendet werden unter anderem die reale Longrun-Historie der letzten vier/acht Wochen, etablierter Wochenumfang, Phase, Wochen bis zum A-Rennen, Recovery und das explizite Nutzermaximum.

### Belastungsvektor statt eine einzige Prozentregel

Für Longruns gilt als vorrangige Designregel: **nicht gleichzeitig mehrere große Belastungsdimensionen erhöhen**. Relevant sind insbesondere Distanz, Dauer, Intensität, MP-Anteil, Höhenmeter und Gesamtwochenumfang.

- Wird die Longrun-Distanz deutlich erhöht, bleibt die Einheit normalerweise easy.
- Wird der Marathonpace-Anteil erhöht, wird die Distanz gegenüber dem unmittelbar vorherigen Longrun normalerweise gehalten oder nur geringfügig erhöht.
- Nach einem Deload darf ein MP-Longrun deshalb bewusst kürzer sein, statt gleichzeitig wieder volle Distanz **und** mehr MP zu verlangen.
- Ein darauffolgender längerer Easy-Longrun darf die Distanzdimension wieder aufbauen.

Dieses alternierende Muster ist **eine konservative Produkt-/Trainingslogik aus progressiver Überlastung, Spezifität und Belastungssteuerung; es ist nicht als direkt experimentell bewiesene überlegene Zwei-Wochen-Sequenz zu verstehen.**

### Longrun-Anteil und 30–35 km

`max_long_run_share` bleibt ein Stress-Guardrail, aber die normale 45-%-Orientierung ist kein universelles Erzeugungslimit mehr. Hat ein Marathonläufer reale jüngere Longruns ab ungefähr 24 km und die Phase/Recovery passen, darf ein history-supported Longrun diese Orientierung vorübergehend überschreiten. Das explizite `max_long_run_km` bleibt dagegen hart. Ein bewusst strenger eingestellter Anteil unter dem normalen 45-%-Default wird weiterhin respektiert.

So kann ein etablierter Läufer mit 28–30-km-Historie auch bei einer moderaten Wochenlast einen sinnvollen 30–35-km-Peak-Longrun erhalten, während ein Läufer mit 18–22-km-Historie nicht auf 34–35 km springt.

### Marathonpace im Longrun

In der spezifischen Phase können ungefähr alle zwei Wochen MP-Blöcke erscheinen, wenn Recovery und Historie passen. Die Dosis wird progressiv aufgebaut; die Engine verwendet keine universell fixe MP-Kilometerzahl. Ein MP-Longrun zählt als harter Reiz und reduziert die andere Qualitätseinheit.

## Goal Marathon Pace vs. Current Estimated Marathon Pace

Die Zielzeit des Nutzers und die aktuelle Leistungsprognose werden getrennt geführt. Trainingsgeschwindigkeiten werden nicht blind aus einer möglicherweise überambitionierten Wunschzeit abgeleitet. `training_paces()` stellt mindestens Goal Marathon Pace, Current Estimated Marathon Pace und die tatsächlich für das Training verwendete Marathonpace getrennt bereit. Mit steigender Leistung darf sich die Trainings-MP schrittweise der Ziel-MP annähern.

## Recovery und adaptive Vorschläge

`RecoveryState` kombiniert mehrere Signale und klassifiziert grün/gelb/rot. HRV und Ruhepuls werden relativ zur persönlichen mehrwöchigen Baseline bewertet; ein einzelner schlechter HRV-Wert darf nicht allein eine rote Entscheidung auslösen. Berücksichtigt werden – soweit vorhanden – HRV-Trend, Ruhepuls, Schlaf, subjektive Erholung, Beine, RPE, Schmerzen/Beschwerden und auffällige Laufreaktionen.

Nach absolvierten Einheiten können vier sehr kurze subjektive Angaben gespeichert werden:

- RPE 1–10
- Beine 1–5
- Schmerzen: nein / leicht / relevant
- Erholung 1–5

Diese Daten sind gleichwertige Inputs neben Wearable-Daten. Detaillierte importierte Läufe können zusätzlich Herzfrequenz, Splits, Höhenprofil, Running Power und weitere vorhandene Laufdynamik liefern. Herzfrequenzdrift wird nur als Schätzung verwendet, wenn die Datenqualität dies zulässt.

Gelbe/rote Readiness verändert den Plan **nicht automatisch**. Sie kann einen normalen Laufapp-Vorschlag zum Reduzieren/Verschieben erzeugen. Umgekehrt können mehrere kontrolliert verträgliche Einheiten bei guter Erholung eine kleine Progression vorschlagen. Auch diese Progression bleibt `pending`, bis der Nutzer sie ausdrücklich übernimmt.

## „Warum diese Einheit?“

Qualitätseinheiten und besondere Longruns speichern `physiological_target`, `variant_key`, `workout_form`, `why`, `load`, Planbasis und rollierende Intensitätsverteilung. Die Wochen-/Workout-Ansicht kann daraus erklären, welcher Reiz beabsichtigt ist und warum beispielsweise ein Longrun bei gleicher Distanz mehr Marathonpace statt mehr Kilometer erhält.

## Evidenzbasis und Grenzen der Evidenz

Die Regeln behandeln die Evidenz als Rahmen, nicht als Quelle scheinpräziser Universalwerte. Als Ausgangsbasis dienen insbesondere die vom Projekt vorgegebenen Publikationen:

- Muniz-Pumares et al., *The Training Intensity Distribution of Marathon Runners Across Performance Levels*, Sports Medicine (2025), PMID **39616560** – große Marathonanalyse, relevant für Umfang und Intensitätsverteilung.
- Casado et al., systematische Übersicht zu Periodisierung, Methoden, Intensitätsverteilung und Volumen bei hochtrainierten Distanzläufern, PMID **35418513**.
- aktuelle Network-Meta-Analyse zu Trainingsintensitätsverteilungen, PMID **39888556** – wichtig gegen die Annahme, polarisiert sei pauschal jedem anderen Modell überlegen.
- systematische Übersicht zu Intensitätsverteilung bei Mittel-/Langstreckenläufern, PMID **34749417**.
- systematische Review/Meta-Analyse zur Programmierung von Intervalltraining, PMID **33826121** – kein einzelnes Intervallformat wird als universell optimal behandelt.
- *Training for a (half-)marathon: Training volume and longest endurance run related to performance and running injuries*, PMID **32421886**.
- Wang et al., Taper-Meta-Analyse, PMID **37163550** – Volumenreduktion bei weitgehend erhaltener Frequenz/Intensität.
- HRV-basierte Trainingsanpassung mit Wearables, PMID **34489178** – unterstützt trend-/kontextbezogene Nutzung statt Einzelwert-Entscheidung.
- Saw et al., subjektives Monitoring, PMID **26423706** – unterstützt die explizite Einbeziehung subjektiver Recovery-/Wellness-Signale.
- Schlafdeprivation und Ausdauerleistung, PMID **36472094**.
- Damsted et al. zu Trainingslaständerungen und Laufverletzungen, PMID **30534459** – Grund, **keine starre 10-%-Regel als wissenschaftlich bewiesen** darzustellen.

Die exakte Rotation „Intervalle → Pyramide → Tempodauerlauf“ ist nicht als wissenschaftlich überlegene Reihenfolge implementiert. Ebenso ist „eine Woche länger, nächste Woche gleiche Länge + MP“ keine direkt bewiesene Universalformel. Beides sind kontrollierte Implementierungsstrategien, die physiologische Kontinuität, Variation, progressive Überlastung und das Vermeiden gleichzeitiger großer Belastungssprünge verbinden.

## Validierung v0.2.0

Die CI führt neben Compile- und JavaScript-Syntaxchecks die vollständige Pytest-Regression, einen eigenständigen 16-Wochen-Marathonsimulator, **neun reproduzierbar randomisierte Läuferprofile**, Docker-Build und Docker-Runtime-Smoke-Test aus. Der feste Simulator erzeugt einen kompletten 16-Wochen-Zyklus, markiert jede Woche synthetisch als absolviert und lässt die nächste Woche aus der entstandenen Historie neu planen.

Die neun Randomprofile verwenden feste Seeds und decken ungefähr **25–100 km etablierte Wochenlast**, **3–7 Lauftage**, **1–3 Qualitätseinheiten**, unterschiedliche 10-km-Leistungsstände, automatische/manuelle Wochenlimits, bewusst niedrige Nutzerlimits, unterschiedliche Longrun-Grenzen, ambitionierte Zielzeiten, Detraining sowie A-/B-/C-Rennkonstellationen ab. Geprüft werden unter anderem:

- Foundation/Build/Recovery/Specific/Taper/Race
- exakte Anzahl und konfliktfreie Datierung der Einheiten
- echte Workoutvariation bei konsistentem physiologischem Ziel
- Qualitätsbudget inklusive intensiver Longruns
- begrenzte VO₂max-Rolle im Build und Rückgang vor dem Rennen
- mehrere Deloads und MP-Longrun-Verteilung
- Longrun-Distanz-vs.-Intensitätsregel
- harte Nutzergrenzen für Wochenumfang und Longrun
- Current-Estimated-Pace-Cap bei ambitionierter Zielzeit
- rollierend überwiegend niedrige Intensität
- B-Renn-Ersatzlogik
- voller 42,195-km-A-Wettkampf am realen Renntag
- robuste SQLite-Datenbankintegrität

Der final geprüfte Branch besteht **78/78 Pytests**, dem separaten 16-Wochen-Simulator, allen neun Randomprofilen, Home-Assistant-Docker-Build und Docker-Runtime-Smoke-Test.

Nicht simuliert werden reale Home-Assistant-/Ingress-/Nabu-Casa-/iPhone-Interaktionen. Daher gilt weiterhin: **Statisch/isoliert getestet; Home-Assistant-Integration muss lokal auf dem Beelink verifiziert werden.**
