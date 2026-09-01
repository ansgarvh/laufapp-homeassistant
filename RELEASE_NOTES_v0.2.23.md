# Laufapp v0.2.23

## KI-Chat und Feedback zu einem einzelnen Lauf

Der bestehende Coach-Tab ist jetzt als echter Mehrturn-Chat nutzbar: Die Laufapp übermittelt neben dem aktuellen Trainingskontext eine begrenzte Auswahl der zuletzt lokal gespeicherten Chatnachrichten. Antworten werden über die OpenAI Responses API mit festem JSON-Schema angefordert. Die lokale Trainingsengine bleibt für Zahlen, Planung und Sicherheitsgrenzen autoritativ.

Unter **Fortschritt** öffnet ein Tipp auf einen Lauf die erweiterten Laufdetails. Dort zeigt Laufapp zunächst lokal berechnete Messwerte wie Pace, Herzfrequenzdrift, Power, Kadenz, Schrittlänge, vertikale Bewegung, Bodenkontaktzeit und – soweit vorhanden – GPS-abgeleitete Kilometersplits. Über **Mit KI analysieren** kann genau dieser Lauf ausdrücklich freigegeben werden.

Die KI-Antwort wird gegliedert in:

- kurze Gesamteinordnung,
- Soll–Ist-Vergleich zur verknüpften Planeinheit,
- Pace und Verlauf,
- Herzfrequenz,
- Laufdynamik,
- Recovery,
- nächsten Schritt,
- Datenqualität und Unsicherheiten.

Die Analyse wird lokal in der bestehenden SQLite-Datenbank gespeichert. Beim erneuten Öffnen erfolgt kein neuer OpenAI-Aufruf. Werden Laufangaben später verändert, kennzeichnet die App die vorhandene Analyse als veraltet; nur die ausdrückliche Aktion **Erneut analysieren** erzeugt eine neue Anfrage. Über **Dazu Coach fragen** lässt sich die Unterhaltung mit einem passenden Entwurf fortsetzen.

## Datenschutz und Sicherheitsgrenzen

- Der API-Key verbleibt in `/data/options.json` der Home-Assistant-App und wird nicht an das Browser-Frontend ausgeliefert.
- Für die Einzelanalyse werden nur lokal berechnete Laufkennwerte, die verknüpfte Planeinheit, kompakte Vergleichsläufe, Wochenlast und relevante Recovery-Aggregate übertragen.
- GPS-Rohkoordinaten und die vollständige Health-Datenbank werden nicht an OpenAI gesendet.
- Alle Responses-Aufrufe setzen `store=false`. Standardmäßige Abuse-Monitoring-Regeln des OpenAI-Projekts können unabhängig davon gelten.
- Laufnotizen und sonstige eingebettete Inhalte werden als unvertraute Daten behandelt.
- Planänderungen bleiben serverseitig validierte Vorschläge. Erst **Übernehmen** verändert eine geplante Einheit; **Ablehnen** verwirft den Vorschlag.
- Ein identischer bereits offener Vorschlag wird nicht dupliziert.
- Das Monatsbudget bleibt standardmäßig auf 10 EUR begrenzt. Coach-Modell ist `gpt-5.6-terra`; die Screenshot-Erkennung nutzt `gpt-5.6-luna`.

## Kompatibilität

Keine Datenbankschemamigration. Bestehende SQLite-Daten, Apple-Health-Import, Health Auto Export, detaillierte Laufmesswerte, GPS-Speicherung, Kalenderregeln, Ingress-Schutz und der unabhängig versionierte Home-Assistant-Relay bleiben unverändert.

## Validierung

- **183/183 Pytests** einschließlich neuer Tests für `store=false`, Structured Outputs, lokalen Chatkontext, minimierte Laufdaten, Ausschluss von GPS-Rohkoordinaten, Analyse-Cache, Stale-Erkennung und bestätigungspflichtige Planänderungen.
- Python-Compilecheck sowie JavaScript- und Shell-Syntaxchecks.
- 16-Wochen-Marathonsimulation und neun randomisierte Läuferprofile.
- SQLite-Integrität, bestehende Migrationspfade und Security-Gates.

Die OpenAI-Aufrufe wurden vollständig gemockt und isoliert getestet; es wurde kein realer API-Key verwendet und es wurden keine Gesundheitsdaten an OpenAI übertragen. Die tatsächliche OpenAI-/Home-Assistant-OS-/Ingress-/iPhone-Darstellung muss nach Installation lokal verifiziert werden.
