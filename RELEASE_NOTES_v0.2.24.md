# Laufapp v0.2.24

## KI & Datenschutz

Die bisher unter **Mehr** angezeigte KI-Statuskarte besitzt jetzt den auswählbaren Menüpunkt **KI & Datenschutz**. Dort lassen sich das Coach-Modell, das Modell für Fitness-Screenshots, das monatliche KI-Budget und die wissenschaftliche Websuche einstellen.

Die empfohlenen Vorgaben bleiben:

- Coach: `gpt-5.6-terra`
- Screenshots: `gpt-5.6-luna`
- Monatsbudget: 10 EUR
- wissenschaftliche Websuche: aktiviert

Der API-Key wird weiterhin ausschließlich über **Home Assistant → Einstellungen → Apps → Laufapp → Konfiguration → openai_api_key** hinterlegt. Das Frontend erhält nur den Status „verbunden“ oder „nicht konfiguriert“ und kann den Key weder lesen noch verändern.

## Datenschutzgrenzen

Die neue Ansicht erklärt direkt in der App:

- Einzelanalysen senden nur den ausgewählten Lauf mit lokal abgeleiteten Kennwerten und kompaktem, unmittelbar relevantem Trainingskontext.
- GPS-Rohkoordinaten und die vollständige Health-Datenbank werden nicht übertragen.
- Screenshots werden nur nach ausdrücklicher Auswahl gesendet und nicht als Bild gespeichert.
- Responses-Aufrufe verwenden `store=false`; abhängig von den OpenAI-Projektregeln können zeitlich begrenzte Abuse-Monitoring-Logs bestehen.
- Analysen werden lokal gespeichert. Planänderungen bleiben bestätigungspflichtige Vorschläge.

## Kompatibilität

Keine Datenbankschemamigration. Trainingsengine, detaillierte Laufdaten, Apple-Health-Hintergrundimport, Health Auto Export, Home-Assistant-Ingress und das separat versionierte Relay bleiben unverändert. Die tatsächliche Home-Assistant-/iPhone-Darstellung muss nach Installation lokal verifiziert werden.

## Validierung

- **185/185 Pytests** bestanden, einschließlich neuer API-Validierungs-, UI-, Datenschutz- und Versionsprüfungen.
- Python-, JavaScript- und Shell-Syntaxchecks bestanden.
- Direkter HTTP-E2E mit Setup, persistierter KI-Konfiguration, ausgelieferten v0.2.24-Assets und Prüfung auf fehlende API-Key-Ausgabe bestanden.
- 16-Wochen-Marathonsimulation und neun randomisierte Läuferprofile bestanden.
- Bandit-Gate, Secret-Scan und Dependency-Konsistenz bestanden.

Docker-Build, Dependency Audit und die vollständigen Home-Assistant-/Ingress-/HAE-E2E-Gates werden zusätzlich durch GitHub Actions ausgeführt.
