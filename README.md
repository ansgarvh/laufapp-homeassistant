# Laufapp v0.2.18

Private, mobile-first Lauf-PWA für Home Assistant OS. Laufapp verbindet eine lokale Trainings-/Prognoseengine mit Apple-Health-Daten, Health Auto Export und einem optionalen OpenAI-Coach. Die Anwendung ist für einen einzelnen privaten Nutzer ausgelegt.


## Neu in v0.2.18 – Wettkampfkalender mit A/B/C-Prioritäten

- Mehrere **A-Rennen** können gleichzeitig hinterlegt werden. Bis zum jeweils chronologisch nächsten A-Rennen steuert ausschließlich dieses Rennen Periodisierung, Peak und Taper; erst danach übernimmt das folgende A-Rennen.
- Nach einem A-Marathon schützt eine automatische **Post-Race-Recovery** die erste Folgewoche; bei engem Abstand zum nächsten A-Rennen folgt ein kontrollierter Wiedereinstieg/Taper statt eines neuen Aufbau-Blocks.
- **B-Rennen** bleiben lokale Sekundärziele und ersetzen nur den Longrun ihrer Rennwoche.
- **C-Rennen** sind Trainingswettkämpfe: kurze C-Rennen ersetzen eine Qualitätseinheit, längere C-Rennen eine lange Einheit; sie erzeugen keinen eigenen Taper und verändern keine vorherigen Wochen.
- Harte **Vergangenheitssperre**: Änderungen am Rennkalender dürfen keine Trainingstage vor dem aktuellen Datum neu erzeugen, löschen oder umplanen. Auch ein manuell mit einem alten Startdatum ausgelöster Plan-Refresh wird auf heute und die Zukunft begrenzt.
- A-Rennen über 5 km, 10 km und Halbmarathon werden in ihrer Rennwoche nun genauso zuverlässig als echte Wettkampfeinheit am tatsächlichen Renndatum erzeugt wie Marathon-A-Rennen.
- Keine Datenbankschemamigration; bestehende Rennen erhalten weiterhin standardmäßig Priorität A, wenn noch keine Priorität gespeichert ist.


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
- Wochenübersicht: 3–7 konfigurierbare Lauftage, Verschieben/Tauschen, Status, Wochenkilometer und Planbegründungen
- Rennen: mehrere A-/B-Rennen mit eigener Zielzeit
- Trainingssteuerung: wissenschaftlich orientierte Periodisierung, Workout-Variation, Deload/Taper, Longrun-/Qualitätsbudget und Planungsaggressivität
- Fortschritt: Prognosen für 5 km, 10 km, Halbmarathon und Marathon, Bestzeiten, Wochenkilometer und die neue 3–24-Monats-Trainingsentwicklung
- Apple Health: manueller ZIP/XML-Import der letzten 24 Monate als Historien-/Fallbackpfad
- detaillierte Laufdaten: HR, Speed, Power, Schrittlänge, vertikale Oszillation, Bodenkontaktzeit, Kadenz, GPS/Höhe soweit vorhanden
- Schuhe: Stammdaten und Kilometerbilanz
- AI Coach: optionaler Chat, Screenshot-Auswertung und ausschließlich bestätigungspflichtige Planänderungen

## Persistenz

Benutzerdaten liegen im persistenten Home-Assistant-`/data`-Bereich. v0.2.18 benötigt **keine Datenbankschemamigration**.

## OpenAI

Der OpenAI-API-Key bleibt serverseitig in der Home-Assistant-App-Konfiguration und wird nicht an das Browser-Frontend ausgeliefert. Laufapp funktioniert für Plan, Prognosen, Health-Import, Wochenübersicht, Läufe, Schuhe und Rennen ohne OpenAI-Key.

## Release-Prüfungen

Vor Merge laufen Python-Compilecheck einschließlich Custom Integration, JavaScript-Syntaxchecks, vollständige Pytest-Regression über den v0.2.15-Entry-Point, realitätsnahe HAE-v2-Regressionstests, >262144-Zeichen-Relaytest, Rate-/Slow-Body-Webhooktests, 16-Wochen-Marathonsimulation, neun randomisierte Läuferprofile, `pip check`, `pip-audit`, Git-History-Secret-Scan, Bandit-Gate, Docker-Build, direkter HAE-E2E, interner Relay-E2E, externe Ingress-Spoofing-Negativtests und positive Home-Assistant-Ingress-Netzsimulation.

Statisch/isoliert und in Linux/Docker getestet. Die echte Home-Assistant-OS-/Custom-Integration-/Nabu-Casa-Remote-UI-/Health-Auto-Export-iPhone-Integration muss nach Installation auf dem Zielsystem lokal verifiziert werden.

## Lokale Entwicklung

```bash
cd laufapp/app
export LAUFAPP_DATA_DIR=/tmp/laufapp-data
export LAUFAPP_TRANSFER_DIR=/tmp/laufapp-transfer
export LAUFAPP_TRUSTED_INGRESS_ONLY=0
export LAUFAPP_HEALTH_AUTO_EXPORT_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
uvicorn main_v0215:app --host 127.0.0.1 --port 8099 --no-proxy-headers
```

Weitere Details: `SECURITY.md`, `NABU_CASA_HEALTH_SYNC.md`, `RELEASE_NOTES_v0.2.18.md`, `TRAINING_ENGINE.md`, `MIGRATIONS.md`.