# Laufapp v0.2.25

Private, mobile-first Lauf-PWA für Home Assistant OS. Laufapp verbindet eine lokale Trainings-/Prognoseengine mit Apple-Health-Daten, Health Auto Export und einem optionalen OpenAI-Coach. Die Anwendung ist für einen einzelnen privaten Nutzer ausgelegt.


## Neu in v0.2.25 – vollständige Laufdetailansicht

- Ein erkannter, absolvierter Lauf öffnet per Klick jetzt eine eigenständige **Laufdetails**-Ansicht – sowohl aus **Fortschritt** als auch direkt aus einer absolvierten Einheit der **Wochenübersicht**.
- Die Ansicht bleibt im hellen Laufapp-Look&Feel und zeigt Strecke, Trainingszeit, verstrichene Zeit, Ø-Pace, Höhenmeter, Ø-Herzfrequenz, Ø-Leistung, Ø-Kadenz, Aktivitätskalorien, Anstrengung, Schrittlänge, vertikale Oszillation und Bodenkontaktzeit, soweit die jeweilige Quelle diese Werte gespeichert hat.
- Zeitaufgelöste Kurven für Höhe, Herzfrequenz, Pace, Leistung, Kadenz, vertikale Oszillation, Bodenkontaktzeit und Schrittlänge werden aus den bereits lokal gespeicherten Messpunkten erzeugt. Große Zeitreihen werden für die Browserdarstellung begrenzt heruntergesampelt, ohne die persistierten Rohdaten zu verändern.
- Vorhandene GPS-Punkte werden als lokale Streckengrafik mit Start-/Endmarkierung dargestellt. Dafür wird bewusst **kein externer Karten-/Tile-Dienst** aufgerufen; GPS-Rohkoordinaten verlassen die Laufapp nicht.
- **Gesamtkalorien** werden nicht aus Aktivitätskalorien hochgerechnet: die bestehenden Apple-Health-/HAE-Pfade speichern bislang keinen separaten Gesamtenergie-Wert pro Lauf. Die Kachel bleibt deshalb transparent leer, statt einen erfundenen Wert zu zeigen.
- Die vorhandenen Funktionen für eigene Laufangaben und **KI-Feedback zu diesem Lauf** bleiben erreichbar und unverändert erhalten.
- Keine Datenbankschemamigration und keine Änderung am separat versionierten Home-Assistant-Relay.


## Neu in v0.2.24 – KI & Datenschutz bedienbar

- Unter **Mehr → KI & Datenschutz** steht jetzt ein ausdrücklich auswählbarer Menüpunkt bereit.
- Coach-Modell, Screenshot-Modell, monatliches KI-Budget und wissenschaftliche Websuche lassen sich dort bearbeiten.
- Die empfohlenen Standardwerte bleiben `gpt-5.6-terra` für den Coach, `gpt-5.6-luna` für Screenshots und 10 EUR Monatsbudget.
- Die Ansicht erläutert konkret, welche Daten bei einer Laufanalyse übertragen werden und welche nicht. GPS-Rohkoordinaten und die vollständige Health-Datenbank bleiben ausgeschlossen.
- Der OpenAI-Key bleibt ausschließlich in der Home-Assistant-App-Konfiguration und wird weder angezeigt noch an den Browser ausgeliefert.
- Es gibt keine Datenbankschemamigration und keine Änderung am separat versionierten Home-Assistant-Relay.


## Neu in v0.2.23 – KI-Chat und Feedback zu einem einzelnen Lauf

- Der **Coach-Chat** nutzt die letzten lokalen Nachrichten als begrenzten Gesprächskontext und liefert schemafeste Antworten über die OpenAI Responses API.
- Jeder Lauf unter **Fortschritt → Laufdetails** kann ausdrücklich über **Mit KI analysieren** ausgewertet werden. Die Antwort gliedert sich in Soll–Ist, Pace/Verlauf, Herzfrequenz, Laufdynamik, Recovery, nächsten Schritt und Datenqualität.
- Für die Einzelanalyse werden lokal berechnete Kennwerte dieses Laufs, die verknüpfte Planeinheit, kompakte Vergleichsläufe, Wochenlast und relevante Recovery-Aggregate übertragen. **GPS-Rohkoordinaten und die vollständige Health-Datenbank werden nicht gesendet.**
- Eine Analyse wird in der bestehenden persistenten SQLite-Datenbank gespeichert und ohne erneuten API-Aufruf wieder angezeigt. Nach geänderten Laufdaten wird sie als veraltet markiert; nur **Erneut analysieren** startet bewusst eine neue Anfrage.
- OpenAI-Antwortspeicherung ist mit `store=false` deaktiviert. Die üblichen API-Abuse-Monitoring-Regeln des gewählten OpenAI-Projekts bleiben davon unberührt.
- KI-Antworten verwenden Structured Outputs. Laufnotizen und andere eingebettete Texte werden ausdrücklich als unvertraute Daten behandelt.
- Der API-Key bleibt ausschließlich in der Home-Assistant-App-Konfiguration. Das Standardbudget bleibt bei 10 EUR/Monat; `gpt-5.6-terra` ist der Coach und `gpt-5.6-luna` liest ausdrücklich hochgeladene Screenshots.
- Planänderungen werden weiterhin nur als serverseitig validierter Vorschlag gespeichert und erst über **Übernehmen** wirksam. Die lokale Trainingsengine bleibt autoritativ.
- Keine Datenbankschemamigration und keine Änderung am separat versionierten Home-Assistant-Relay.


## Neu in v0.2.22 – Kalenderabstände und letzter Datenabgleich

- Liegen eine automatisch geplante Qualitätseinheit und ein Easy Run an zwei direkt aufeinanderfolgenden Lauftagen, plant die Engine normalerweise zuerst die Qualitätseinheit und anschließend den Easy Run.
- Zwischen Schlüsselbelastungen werden möglichst mindestens 48 Stunden eingeplant. Da die App Trainingstage, aber keine Startuhrzeiten plant, entspricht dies mindestens zwei Kalendertagen Abstand.
- Qualitätseinheiten, Race-Prep und Rennen gelten als Schlüsselbelastung. Zusätzlich zählen spezifische Longruns sowie sehr lange Longruns ab 24 km oder geschätzten 120 Minuten dazu.
- Automatisch korrigiert werden nur zukünftige, weiterhin geplante und unveränderte Engine-Slots für Easy, Quality und Race-Prep. Longrun-/Renntage sowie manuell verschobene, absolvierte, ausgefallene oder verknüpfte Einheiten bleiben geschützt; nicht lösbare Konflikte erscheinen im Safety Check.
- Der Tab **Heute** zeigt direkt oberhalb von **Nächste Einheit** Datum, Uhrzeit und Quelle der jüngsten erfolgreichen Synchronisierung aus Health Auto Export oder einem abgeschlossenen Apple-Health-ZIP/XML-Import. Fehlgeschlagene oder laufende Importe zählen nicht.
- Der UTC-Zeitpunkt wird mit deutscher Formatierung in der lokalen Browserzeit dargestellt; vor der ersten erfolgreichen Synchronisierung erscheint ein klarer Leerzustand.
- Der Ingress-robuste Header-Icon-Fix aus v0.2.21 bleibt vollständig erhalten. Keine Datenbankschemamigration und keine Änderung am unabhängig versionierten Home-Assistant-Relay.


## Neu in v0.2.21 – Header-Icon Ingress-robust

- Das freigegebene schwarze/neon-grüne Laufmotiv wird im sichtbaren Header jetzt direkt als PNG-Data-URI eingebettet und benötigt keinen separaten Bildrequest mehr.
- Damit kann Home Assistant Ingress bzw. ein relativer Asset-Pfad nicht mehr zu einem Broken-Image-Symbol mit Fragezeichen anstelle des Lauf-Icons führen.
- PWA-Manifest, Apple-Touch-Referenz und Service-Worker-Cache wurden auf v0.2.21 cache-busted.
- Neue Regression dekodiert das eingebettete PNG vollständig und prüft dessen feste SHA-256-Prüfsumme; die externen PWA-PNGs werden zusätzlich auf Chunk-CRC und vollständige IDAT-Dekompression geprüft.
- Keine Datenbankschemamigration und keine Änderung an Trainingsengine, HAE/Nabu/Ingress-Security oder dem unabhängig versionierten Home-Assistant-Relay.


## Neu in v0.2.20 – freigegebenes Laufapp-Icon

- Das bisher im Header per CSS gezeichnete abstrakte Laufzeichen wurde durch das freigegebene schwarze Icon mit neon-grünem Läufer und drei horizontalen Bewegungslinien ersetzt.
- Dasselbe Motiv wird für Header, PWA-Icons in 192/512 Pixeln und das Apple-Touch-Icon verwendet.
- PWA-Manifest und Service-Worker-Cache wurden cache-busted, damit das alte Symbol nicht aus einem Browser-/Homescreen-Cache weiterverwendet wird.
- Das zuvor referenzierte, aber fehlende `apple-touch-icon.png` ist nun vorhanden.
- Reines UI-/Asset-Release: keine Datenbankschemamigration und keine Änderung an Trainingsengine, HAE/Nabu/Ingress, Security oder dem unabhängig versionierten Home-Assistant-Relay.


## Neu in v0.2.19 – manuelle Absolvierung zurücknehmen

- Eine ohne verknüpften Lauf manuell als **absolviert** markierte Einheit kann im Einheiten-Menü über **„Absolvierung zurücknehmen“** wieder auf `geplant` gesetzt werden.
- Ein tatsächlich verknüpfter Lauf bleibt autoritativ: Solange `linked_run_id` gesetzt ist, verhindert das Backend das Zurücksetzen auf `geplant` oder `ausgefallen`, damit Planstatus und Laufdaten nicht widersprüchlich werden.
- Die Rücknahme löscht keine Einheit und keine Laufdaten. Die Einheit bleibt als manuell berührt geschützt (`manual_override=1`).
- Keine Datenbankschemamigration; Trainingsengine, Mehrfachrennen, HAE/Nabu/Ingress und Security bleiben unverändert.


## Neu in v0.2.18 – mehrere Wettkampfziele und bessere Rennanlage

- **Mehrere A-Rennen chronologisch:** Bis zum früheren A-Rennen steuert ausschließlich dieses Ziel die Periodisierung. Ein späteres A-Rennen verändert Aufbau, Peak oder Taper vor dem früheren A-Rennen nicht.
- **Sauberer Übergang zwischen nahen A-Rennen:** Nach einem A-Rennen übernimmt das nächste A-Ziel, aber zuerst mit Recovery-/Übergangsblock. Bei einem engen Abstand wie Marathon → 19 Tage → Halbmarathon folgt auf die Marathon-Rennwoche zunächst Recovery, danach eine kurze Aktivierungs-/Taperphase und erst dann die nächste Rennwoche.
- **A-Rennen für alle Standarddistanzen:** 5 km, 10 km, Halbmarathon und Marathon werden in ihrer A-Rennwoche als exakter Wettkampf am eingetragenen Datum und mit der vollständigen Wettkampfdistanz geplant.
- **A/B/C-Prioritäten:** A steuert die Periodisierung; B ersetzt nur den Longrun seiner Rennwoche; C ersetzt nur eine Qualitätseinheit (ersatzweise einen Easy Run) und lässt Longrun sowie A-Periodisierung bestehen.
- **Wettkampfart als Dropdown:** 5 km, 10 km, Halbmarathon und Marathon können zusätzlich zur exakten Distanz ausgewählt werden. Die Auswahl belegt die Standarddistanz vor, die Distanz bleibt editierbar.
- **Deutsches Dezimalkomma:** Distanzen wie `21,0975` oder `10,25` können jetzt direkt eingegeben werden; Punkt und Komma werden akzeptiert.
- Keine Datenbankschemamigration; Priorität und Wettkampfart bleiben kompatibel in den bestehenden Einstellungen gespeichert.


## Neu in v0.2.17 – verständliches Leistungsprofil

- Das 0–100-Profil erklärt jetzt direkt, dass es eine relative Zielabdeckung und **kein Prozentwert der maximalen Fitness** ist.
- Neue Bereiche: **Ausdauerbasis**, **Speed-Ausdauer**, **Schwellen-Ausdauer**, zielspezifische **Readiness** und **Trainingskontinuität**.
- Jeder Score zeigt seine Datengrundlage und Teilkomponenten.
- Wochenumfang, Zeit auf den Beinen, Longrun-Historie, Planerfüllung und – bei ausreichender Datenlage – Pace/HF-Trends verknüpfter Easy-Läufe fließen ein.
- Ruhepuls, HRV, Schlaf und VO₂max werden als Health-Kontext angezeigt, aber nicht pauschal in den Score eingerechnet.
- Keine Datenbankschemamigration.

Details zur Berechnung: `PERFORMANCE_PROFILE.md`.


## Neu in v0.2.16 – robuste Aktivitätszuordnung
- Automatische Zuordnung nur, wenn die gelaufene Distanz mindestens 90 % der geplanten Distanz erreicht.
- Übererfüllung bleibt erlaubt: z. B. 20 km tatsächlich bei 15 km geplant wird automatisch verknüpft.
- Kürzere Läufe unter 90 % bleiben unverknüpft und können im Lauf-Menü explizit über **„Aktivität verknüpfen“** einer Planaktivität desselben Tages zugeordnet werden.
- Keine Datenbankschemamigration.


## Neu in v0.2.15 – Wochen-Navigation und Abschlussstatus korrigiert

- **Pfeile am Wochenzeitraum:** Vorherige/nächste Woche stehen jetzt zusammen mit dem Datumsbereich direkt oberhalb der sieben Tagesfelder; „Aktuelle Woche“ bleibt verfügbar, verschiebt den rechten Pfeil aber nicht mehr aus dieser Zeile.
- **Absolviert-Haken zuverlässig:** Der grüne Haken wird direkt aus dem vom Backend gelieferten Workout-Status `completed` gerendert. Die fehleranfällige nachträgliche Erkennung über sichtbaren Text und `MutationObserver` ist aus dem aktiven Frontend entfernt.
- **Status-Roundtrip getestet:** `completed`/`skipped` werden über die bestehende API persistent gespeichert und von `/api/week` nach dem Neuladen wieder ausgegeben.
- Keine Datenbankschemamigration, keine Änderung an Trainingsengine, Health Auto Export, Nabu-Casa-Relay oder den Security-Grenzen.

## Neu in v0.2.14 – Wochenübersicht klarer

- **Absolvierte Einheiten sofort sichtbar:** Sobald eine Einheit über „Als absolviert markieren“ den Status `completed` erhält, zeigt die Wochenkarte links einen grünen Haken. Die vorhandene Textkennzeichnung „absolviert“ bleibt zusätzlich bestehen.
- **Wochenzeitraum an den Tagen:** Der Datumsbereich der Trainingswoche steht nicht mehr in der oberen Navigationsleiste, sondern direkt oberhalb der sieben Tagesfelder. Die Vor-/Zurück-Navigation und „Aktuelle Woche“ bleiben unverändert.
- Reines UI-Release: keine Datenbankschemamigration, keine Änderung der Trainingsengine und keine Änderung des HAE-Datenpfads. Die Security-Härtungen aus v0.2.13 bleiben vollständig aktiv.

## Neu in v0.2.13 – Security-Härtung, Bereinigung und Trainingsentwicklung

v0.2.13 baut auf dem nach realem HAE-Export bestätigten v0.2.12-Stand auf und reduziert gezielt Angriffsfläche, ohne Trainingslogik oder persistente Daten zu verändern.

- **Öffentlicher HAE-Webhook begrenzt:** zusätzlich zum 16-MiB-Limit gelten 120 Sekunden Body-Read-Timeout, maximal 12 Requests pro Minute und maximal drei parallele Weiterleitungen. Die feste interne Ziel-URL, POST-only, starke Webhook-ID und der separate Laufapp-Token bleiben bestehen.
- **Browser/API-Härtung:** Cross-Site-Schreibrequests mit `Sec-Fetch-Site: cross-site` werden blockiert. Die Hauptapp setzt `nosniff`, `no-referrer`, eine restriktive Permissions-Policy und eine CSP für lokale Skripte/Styles/Requests.
- **Unnötige Home-Assistant-Rechte entfernt:** der nur für den längst abgeschlossenen einmaligen GitHub-Umzug benötigte `/share:rw`-Mount entfällt. Der alte öffentlich aufrufbare Transfer-Vorbereitungsendpunkt wird nicht mehr registriert.
- **API-Ressourcenlimit ergänzt:** Coach-Historie ist serverseitig auf 1–200 Einträge begrenzt.
- **Repository bereinigt:** alte Jinja/`rest_command`-Relay-Beispiele und `.DS_Store`-Dateien entfernt; `.gitignore` schützt lokale Daten/Secrets künftig besser.
- **Security-CI erweitert:** vollständige Git-Historie wird auf typische OpenAI-/GitHub-/JWT-/Private-Key-/Nabu-Casa-Secrets geprüft; `pip check`, `pip-audit` und Bandit bleiben Gates.
- **Trainingsentwicklung unter Fortschritt:** neue Wochen-Zeitachse für 3, 6, 12 oder 24 Monate. Wählbar sind Laufkilometer, distanzgewichtete Pace, Kadenz, Laufzeit, Läufe/Woche, Ø Laufdistanz, längster Lauf, Herzfrequenz, RPE, Höhenmeter sowie – soweit vorhanden – Ruhepuls, HRV, Schlaf, Gewicht und VO₂max. Fehlende Messwerte werden als Lücken belassen und nicht geschätzt.
- **Keine Datenbankschemamigration:** bestehende Läufe, Health-Daten, Bestzeiten, Schuhe, Rennen, Trainingsplan, Einstellungen und Coach-Daten bleiben erhalten.

## Health Auto Export

Der v0.2.12-Fix für reale deutsche HAE-v2-Workouts bleibt vollständig erhalten. `Outdoor Ausführen` und `Indoor Ausführen` werden als Lauf erkannt; bestehende englische/deutsche Running-/Lauf-Bezeichnungen bleiben kompatibel. Ein vorhandenes `activeEnergyBurned`-Summenfeld bleibt maßgeblich, andernfalls kann eine valide `activeEnergy[]`-Zeitreihe aggregiert werden. `totalEnergy` wird nicht als aktive Energie missinterpretiert.

Der Transport bleibt:

`iPhone / HAE → HTTPS → <remote-id>.ui.nabu.casa/api/webhook/<secret-id> → Home Assistant Custom Integration → internes App-Netz → Laufapp`

Empfohlene Lauf-Automation:

- Automation: REST API
- Ziel-URL: `https://<remote-id>.ui.nabu.casa/api/webhook/<secret-webhook-id>`
- Format: JSON, Export Version 2
- Zeitraum: **Previous 7 Days / Letzte 7 Tage**
- Daten: Workouts → Running
- Route Data / GPX-Routen einschließen: **On**
- Workout Metrics: On
- Workout Metrics Time Grouping: Seconds
- Batch Requests: On
- Kein Laufapp-Token im iPhone-Request; Home Assistant ergänzt ihn erst intern.

Für Ruhepuls, HRV, Gewicht, VO₂max und Schlaf empfiehlt sich eine zweite, weniger häufige Health-Metrics-Automation mit überlappendem 7-Tage-Fenster.

Die vollständige Einrichtung steht in `NABU_CASA_HEALTH_SYNC.md`. Aktuell benötigt wird nur noch `home_assistant/laufapp_hae_relay_configuration.yaml.example`; die früheren Automation-/`rest_command`-Beispiele wurden entfernt.

## Security-Basis

- Port **8099** bleibt Home-Assistant-Ingress-only und ist nicht als Host-Port veröffentlicht.
- Port **8100** bleibt unveröffentlicht und startet nur mit einem starken Health-Auto-Export-Token.
- Uvicorn läuft ohne Proxy-Header-Vertrauen.
- Health Auto Export authentifiziert vor dem Body-Lesen, ist JSON-only und besitzt Größen-, Zeit-, Mengen-, Rate- und Parallelitätslimits.
- Öffentliche Webhook-ID und Laufapp-Token sind getrennte Geheimnisse.
- Die Custom Integration besitzt ein fest verdrahtetes internes Ziel und kann nicht als beliebiger HTTP-Proxy genutzt werden.
- Der klassische Apple-Health-ZIP/XML-Pfad behält ZIP-Bomb-Limits, Dateigrößen-/Punktgrenzen und `defusedxml`-Schutz.
- `/share` wird nicht mehr in den Laufapp-Container gemountet.
- Security-CI umfasst Dependency-Audit, Dependency-Konsistenz, Bandit, Git-History-Secret-Scan, externe Spoofing-Negativtests, positive Home-Assistant-Ingress-Simulation und den internen HAE-Relay-Pfad.

Ausführliche Details und verbleibende Risiken stehen in `SECURITY.md` und `NABU_CASA_HEALTH_SYNC.md`.

## Importdiagnose / Ingress

- Erfolgreiche `/api/health`- und Gateway-`/health`-Polls werden aus dem Uvicorn-Access-Log gefiltert; fehlerhafte Health-Requests und andere API-Aufrufe bleiben sichtbar.
- Phasenwechsel/Fortschritt jedes Apple-Health-Imports werden als JSONL unter `/data/import_status/<job-uuid>.diagnostics.jsonl` gespeichert.
- Background-Job-Fehler speichern Exception-Typ, letzte Phase, Fortschritt, Detaildaten und vollständigen Python-Traceback.
- Port 8099 bleibt Home-Assistant-Ingress-only. Der dokumentierte Proxy `172.30.32.2` sowie der eng begrenzte authentifizierte Kompatibilitätspfad innerhalb `172.30.32.0/23` bleiben erhalten.

## Bestehende Funktionen

- Heute: Planfokus, Zielzeit, Prognose, nächste Einheit, Recovery-Signale und Coach-Vorschläge
- Wochenübersicht: 3–7 konfigurierbare Lauftage, Verschieben/Tauschen, Status, Wochenkilometer und Planbegründungen; absolvierte verknüpfte Läufe öffnen die Laufdetailansicht
- Rennen: mehrere A-/B-/C-Rennen mit eigener Zielzeit, Wettkampfart und exakter Distanz
- Trainingssteuerung: wissenschaftlich orientierte Periodisierung, Workout-Variation, Deload/Taper, Longrun-/Qualitätsbudget und Planungsaggressivität
- Fortschritt: Prognosen für 5 km, 10 km, Halbmarathon und Marathon, Bestzeiten, Wochenkilometer, 3–24-Monats-Trainingsentwicklung und detaillierbare gespeicherte Läufe
- Apple Health: manueller ZIP/XML-Import der letzten 24 Monate als Historien-/Fallbackpfad
- detaillierte Laufdaten: HR, Speed/Pace, Power, Schrittlänge, vertikale Oszillation, Bodenkontaktzeit, Kadenz, GPS/Höhe soweit vorhanden; lokale Verlaufskurven und GPS-Streckengrafik
- Schuhe: Stammdaten und Kilometerbilanz
- AI Coach: optionaler Chat, Screenshot-Auswertung und ausschließlich bestätigungspflichtige Planänderungen

## Persistenz

Benutzerdaten liegen im persistenten Home-Assistant-`/data`-Bereich. v0.2.25 benötigt **keine Datenbankschemamigration**.

## OpenAI

Der OpenAI-API-Key bleibt serverseitig in der Home-Assistant-App-Konfiguration und wird nicht an das Browser-Frontend ausgeliefert. API-Antwortspeicherung ist mit `store=false` abgeschaltet. Standardmäßige Abuse-Monitoring-Logs können abhängig von den Datenkontrollen des OpenAI-Projekts dennoch zeitlich begrenzt verarbeitet werden. Laufapp funktioniert für Plan, Prognosen, Health-Import, Wochenübersicht, Läufe, Schuhe und Rennen vollständig ohne OpenAI-Key.

## Release-Prüfungen

Vor Merge laufen Python-Compilecheck einschließlich Custom Integration, JavaScript-Syntaxchecks, vollständige Pytest-Regression über den v0.2.25-Entry-Point, Laufdetail-/GPS-/Zeitreihen-/Downsampling-Regressionen, KI-Einstellungs-/Validierungs-/Datensparsamkeitsprüfungen, Kalender-/Synchronisationsregressionen, realitätsnahe HAE-v2-Regressionstests, >262144-Zeichen-Relaytest, Rate-/Slow-Body-Webhooktests, PNG-Decode-/Inline-Brand-Regression, 16-Wochen-Marathonsimulation, neun randomisierte Läuferprofile, `pip check`, `pip-audit`, Git-History-Secret-Scan, Bandit-Gate, Docker-Build, direkter HAE-E2E, interner Relay-E2E, externe Ingress-Spoofing-Negativtests und positive Home-Assistant-Ingress-Netzsimulation.

Statisch/isoliert und in Linux/Docker getestet. Die echte Home-Assistant-OS-/Custom-Integration-/Nabu-Casa-Remote-UI-/Health-Auto-Export-iPhone-Integration muss nach Installation auf dem Zielsystem lokal verifiziert werden.

## Lokale Entwicklung

```bash
cd laufapp/app
export LAUFAPP_DATA_DIR=/tmp/laufapp-data
export LAUFAPP_TRANSFER_DIR=/tmp/laufapp-transfer
export LAUFAPP_TRUSTED_INGRESS_ONLY=0
export LAUFAPP_HEALTH_AUTO_EXPORT_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
uvicorn main_v0225:app --host 127.0.0.1 --port 8099 --no-proxy-headers
```

Weitere Details: `SECURITY.md`, `NABU_CASA_HEALTH_SYNC.md`, `RELEASE_NOTES_v0.2.25.md`, `TRAINING_ENGINE.md`, `MIGRATIONS.md`.
