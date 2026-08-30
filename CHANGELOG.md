# Laufapp Changelog

## v0.2.11 – 2026-08-30

- Reale HAE-Großpayload-Grenze behoben: detaillierte Sekunden-Workouts scheiterten im v0.2.10-Automationspfad an Home Assistants `Template output exceeded maximum size of 262144 characters`.
- Neue Custom Integration `custom_components/laufapp_hae_relay` registriert einen direkten POST-only Home-Assistant-Webhook und leitet den Roh-JSON-Body ohne Jinja/`rest_command` an den internen Laufapp-Relay weiter.
- Für den Produktionspfad wird die bereits real erreichbare Nabu-Casa-Remote-UI-URL `https://<id>.ui.nabu.casa/api/webhook/<secret-id>` genutzt; der dedizierte `hooks.nabu.casa`-Cloudhook hatte den echten großen HAE-Request in der Zielinstallation mit HTTP 413 abgewiesen.
- Der Custom Relay akzeptiert nur JSON, begrenzt auf 16 MiB, besitzt das feste interne Ziel `c87ed7df-laufapp:8100`, ist POST-only, ergänzt den separaten starken internen Token und loggt weder Payload noch Secrets.
- Ports 8099 und 8100 bleiben unveröffentlicht; es wird keine neue Host- oder Router-Portfreigabe benötigt.
- Die alte Automation und der `rest_command` bleiben nur als Legacy-Kleinpayload-Diagnose; `local_only: false` wurde dort zugleich für die externe Remote-UI-Nutzung korrigiert.
- Keine Datenbankschemamigration und keine Änderung an Trainingslogik, Prognosen, Bestzeiten, Apple-Health-Historienimport, HAE-Parser/Deduplizierung oder Ingress-Sicherheitslogik.
- Neue Tests prüfen >262144-Byte-Forwarding, 16-MiB-Grenze, Content-Type, Secret-Validierung, POST-only-Registrierung und Duplicate-ID-Fail-Closed; die Custom Integration wird mitkompiliert und von Bandit gescannt.
- Statisch/isoliert und in Linux/Docker getestet; die reale End-to-End-Integration des neuen Custom Components mit Home Assistant OS, Nabu Casa Remote UI und Health Auto Export auf dem iPhone muss nach Installation auf dem Zielsystem verifiziert werden. Die vorhandenen realen Tests haben Remote UI → Home Assistant sowie Home Assistant → Laufapp bereits getrennt bestätigt.

## v0.2.10 – 2026-08-30

- Kontinuierliche Health-Auto-Export-Synchronisation kann nun über **Nabu Casa Cloud Webhooks** erfolgen: iPhone → HTTPS-Cloudhook → Home Assistant → Supervisor-internes App-Netz → Laufapp. Für diesen Betriebsweg sind weder dauerhaftes VPN auf dem iPhone noch eine Router-Portfreigabe nötig.
- Neuer dedizierter interner Gateway-Endpunkt `POST /home-assistant-relay`. Er akzeptiert ausschließlich den separaten starken `X-Laufapp-Token`; ein Bearer-Token allein wird bewusst abgewiesen. Der bestehende direkte `/health-auto-export`-Pfad bleibt kompatibel erhalten.
- Port 8100 bleibt in der Add-on-Konfiguration standardmäßig **unveröffentlicht**. Home Assistant adressiert den Relay-Pfad über den Supervisor-internen DNS-Namen `c87ed7df-laufapp`; nach erfolgreichem realem Cloudhook-Test soll eine temporäre Host-Port-Zuordnung wieder entfernt werden.
- Home-Assistant-Beispiele für `rest_command`, Webhook-Automation und `secrets.yaml` ergänzt. Cloudhook-ID und Laufapp-Token bleiben getrennte Geheimnisse; der reale Token wird nicht in Automation oder Repository eingebettet.
- Für den Nabu-Casa-Pfad wird ein überlappendes **„Previous 7 Days / Letzte 7 Tage“**-Fenster empfohlen. Damit kann ein temporärer Fehler nach der Webhook-Annahme beim nächsten Lauf nachgeholt werden; bestehende Workout-/Sample-/GPS-/Health-Metric-Deduplizierung hält Wiederholungen idempotent.
- Die Beispielautomation verarbeitet HAE-Batches seriell als `mode: queued` mit maximal 50 Einträgen. Erfolgreiche Relay-Imports erzeugen nur einen datensparsamen `LAUFAPP_HAE_RELAY_OK`-Marker mit Importzählern, ohne Token, Cloudhook-ID oder persönliche Messwerte.
- Keine Datenbankschemamigration und keine Änderung an Trainingslogik, Prognosen, Bestzeiten, Apple-Health-Historienimport oder v0.2.9-Ingress-Sicherheitslogik.
- Validierung des vorletzten Branch-Stands: **119/119 Pytests**, Python-Compilecheck, JavaScript-Syntax, Dependency-Audit, 16-Wochen-Marathonsimulation, neun randomisierte Läuferprofile, Docker-Build, direkter HAE-E2E, interner Nabu-Relay-E2E, Ingress-Sicherheits-E2E und Gateway-fail-closed erfolgreich; Security-Workflow ebenfalls erfolgreich. Der finale Release-Metadatenstand wird vor Merge erneut vollständig geprüft.
- Statisch/isoliert und in Linux/Docker getestet; reale Home-Assistant-/Supervisor-/Nabu-Casa-/Health-Auto-Export-iPhone-Integration muss lokal auf dem Beelink verifiziert werden.

## v0.2.9 – 2026-08-30

- Browser-/Ingress-Erreichbarkeit korrigiert: Der in v0.2.7 eingeführte ausschließlich auf `172.30.32.2` fixierte Ingress-Guard erhält einen eng begrenzten Kompatibilitätspfad für reale Home-Assistant-interne Peers.
- Der dokumentierte Home-Assistant-Ingress-Proxy `172.30.32.2` bleibt direkt zugelassen. Andere Peers werden ausschließlich innerhalb des internen Netzes `172.30.32.0/23` akzeptiert und benötigen zusätzlich einen `X-Ingress-Path` unter `/api/hassio_ingress/` sowie einen Authentifizierungsmarker (`X-Remote-User-Id` oder `X-Hass-Source: core.ingress`).
- Externe/Host-seitige Clients bleiben selbst mit gefälschtem `X-Forwarded-For`, `X-Hass-Source`, `X-Ingress-Path` und `X-Remote-User-Id` gesperrt; Uvicorn vertraut weiterhin keine Proxy-Header und Port 8099 bleibt unveröffentlicht.
- Blockierte Zugriffe werden über `LAUFAPP_INGRESS_BLOCKED` diagnostizierbar. Geloggt werden Peer-IP, Pfad und nur boolesche Angaben zum Vorhandensein relevanter Ingress-Marker; Benutzer-IDs oder Tokens werden nicht protokolliert.
- Neue positive Docker-E2E-Prüfung erzeugt ein eigenes `172.30.32.0/23`-Netz und prüft: Zugriff vom kanonischen `.2`-Proxy, Zugriff eines anderen internen Peers mit authentifizierten Ingress-Markern sowie HTTP 403 ohne diese Marker.
- Bestehende v0.2.8-Importdiagnose, vollständige Background-Tracebacks, Shutdown-/Child-Exit-Logging und sämtliche Health-Auto-Export-Sicherheitsmechanismen bleiben erhalten.
- Keine Datenbankschemamigration und keine Änderung an Trainingslogik, Prognosen, Apple-Health-Daten, GPS/Samples oder Bestzeiten.
- Statisch/isoliert und in Linux/Docker getestet; reale Home-Assistant-/Supervisor-Integration muss nach Installation auf dem Beelink verifiziert werden.

## v0.2.8 – 2026-08-30

- Erfolgreiche `/api/health`- und Gateway-`/health`-Polls werden aus dem Uvicorn-Access-Log gefiltert, damit Supervisor-/Watchdog-Abfragen relevante Fehler nicht mehr aus dem Logpuffer verdrängen; fehlgeschlagene Health-Requests und alle anderen API-Aufrufe bleiben sichtbar.
- Jeder Apple-Health-Hintergrundjob erhält eine persistente, begrenzte Diagnosehistorie unter `/data/import_status/<job-uuid>.diagnostics.jsonl` mit Queue-/Start-/Fortsetzungs-/Retry-/Abschlussereignissen sowie Phasenwechseln, Fortschritt und Importdetailzählern.
- Background-Importfehler speichern nun Exception-Typ, letzte bekannte Phase, Fortschritt, Detaildaten und den vollständigen Python-Traceback dauerhaft; derselbe Traceback wird zusätzlich mit Job-ID und Phase nach stderr geschrieben.
- Neuer Ingress-geschützter Diagnoseendpunkt `GET /api/apple-health/import-jobs/{job_id}/diagnostics`; der separat erreichbare Health-Auto-Export-Gateway exponiert diese Read-Daten weiterhin nicht.
- Unterbrochene Importe protokollieren beim Neustart explizit `resumed_after_restart`. `run.sh` protokolliert außerdem Prozessstarts, SIGTERM/SIGINT sowie PID und Exitstatus des Main- oder Gateway-Prozesses, bevor das Add-on beendet wird.
- Keine Datenbankschemamigration und keine Änderung an Trainingslogik, Apple-Health-Deduplication, Transaktions-/Rollback-Verhalten, detaillierten Samples, GPS-Daten oder Bestzeitenlogik.
- Release-Gates erweitert: Produktions-Entry-Point v0.2.8 wird in der Regression verwendet; zusätzliche Tests decken persistente Diagnose, vollständige Tracebacks, Wiederaufnahme nach Neustart, Healthcheck-Logfilter und Shell-Syntax ab.
- Validierung des vorletzten Branch-Stands: Laufapp CI #171 und Laufapp Security #16 erfolgreich. Der finale Dokumentationscommit wird vor Merge erneut vollständig geprüft.
- Statisch/isoliert und in Linux/Docker getestet; reale Home-Assistant-/Supervisor-/Nabu-Casa-/VPN-/Health-Auto-Export-iPhone-Integration muss lokal auf dem Beelink verifiziert werden.

## v0.2.7 – 2026-08-30

- Home-Assistant-Ingress-Vertrauensgrenze gehärtet: Uvicorn vertraut keine beliebigen Proxy-Header mehr; in Produktion wird ausschließlich die reale TCP-Quelle des Home-Assistant-Ingress-Proxys `172.30.32.2` akzeptiert, Loopback nur für `/api/health`. Gefälschte `X-Forwarded-For`-/Ingress-Header werden in einem Docker-Negativtest explizit abgewehrt.
- Health-Auto-Export-Gateway arbeitet fail closed und startet Port 8100 nur mit einem starken, mindestens 48 Zeichen langen zufälligen Token. Authentifizierung erfolgt vor dem Body-Lesen; JSON-Content-Type, 16-MiB-Streaminglimit, 120-Sekunden-Timeout, Mengenlimits und begrenzte Parallelität schützen gegen Request-/Memory-/Slow-Request-DoS.
- Gateway-Angriffsfläche minimiert: OpenAPI/Swagger/ReDoc deaktiviert, Server-Header deaktiviert, `no-store`/`nosniff`/`no-referrer`, write-only Antwort ohne Prognosen oder persönliche Read-Daten.
- Workout-ID-Kollisionsschutz und Cross-Source-Deduplizierung verhindern widersprüchliche Wiederverwendung sowie Doppelwerte beim Übergang vom klassischen Apple-Health-Import zu Health Auto Export.
- Klassischer Apple-Health-ZIP/XML-Pfad gehärtet: ZIP-Bomb-/Dateianzahl-/GPX-Größen-/Punktlimits, GPS-Plausibilisierung und `defusedxml` gegen XML-Entity-Expansion/externe XML-Referenzen.
- Dependency-Audit identifizierte bekannte Sicherheitslücken in der zuvor verwendeten Starlette-Version 0.50.0. Runtime-Stack auf FastAPI 0.141.1 / Starlette 1.6.0 aktualisiert; direkte Runtime-Abhängigkeiten gepinnt und `pip-audit` als Release-Gate ergänzt.
- Bandit-Security-Scan mit review-bewusstem Gate ergänzt; neue Medium/High-Findings blockieren die CI. GitHub Actions sind auf konkrete Commit-SHAs gepinnt und besitzen nur `contents: read`.
- Dynamische Frontend-Renderpfade auf Stored/Reflected XSS geprüft; im geprüften Pfad keine offene XSS-Lücke gefunden.
- Keine Datenbankschemamigration und keine fachliche Änderung der Trainingslogik.
- Statisch/isoliert und in Linux/Docker getestet; reale Home-Assistant-/Supervisor-/VPN-/Health-Auto-Export-iPhone-Integration muss lokal verifiziert werden.

## v0.2.6 – 2026-08-30

- Release-Linie funktional wieder auf den vollständig getesteten v0.2.5-Stand gesetzt; die zwischenzeitlich entwickelte native v0.3.0-iOS-/HealthKit-App und deren macOS-CI-Pfad wurden entfernt.
- **Health Auto Export JSON Export Version 2** als kontinuierliche Apple-Health-Schnittstelle ergänzt. Unterstützt werden Laufworkouts mit stabiler Workout-ID, Start/Ende, Dauer, Distanz, Kalorien, Höhenmetern und mittlerer Herzfrequenz.
- Detaillierte Workoutdaten werden in den bestehenden v0.2.5-Strukturen gespeichert: Herzfrequenz, Running Speed, Running Power, Schrittlänge, vertikale Oszillation, Bodenkontaktzeit, dokumentierte Workout-Kadenz sowie GPS-Route/Höhe.
- Allgemeine Health-Metriken unterstützen Ruhepuls, HRV/SDNN, Gewicht, VO₂max und Schlafdauer.
- Wiederholte Zustellung ist über Workout-ID und deterministische Sample-/Metric-IDs idempotent; neue Läufe werden wie bisher mit dem Trainingsplan gematcht und anschließend Bestzeiten und Prognosen aktualisiert.
- Hauptanwendung bleibt **Home-Assistant-Ingress-only** auf Port 8099. Ein separater minimaler, tokenpflichtiger Sync-Gateway auf Port 8100 stellt nur `/health` und `POST /health-auto-export` bereit und ist standardmäßig nicht veröffentlicht.
- Neues Secret `health_auto_export_token` als Home-Assistant-Passwortoption; Bearer- oder `X-Laufapp-Token`-Authentifizierung mit timing-resistentem Vergleich. Größen- und Mengenlimits schützen die Importstrecke.
- Port 8100 ist nur für bewusst abgesicherten LAN-/VPN-/HTTPS-Betrieb vorgesehen und darf nicht unverschlüsselt ins Internet weitergeleitet werden.
- Keine Datenbankschemamigration. Bestehende v0.2.5-Daten und der manuelle Apple-Health-ZIP/XML-Import bleiben vollständig erhalten.
- Validierung: Python-Compilecheck, JavaScript-Syntaxchecks, vollständige Pytest-Regression, 16-Wochen-Marathonsimulation, neun randomisierte Läuferprofile, Docker-Build sowie Docker-Runtime-E2E mit abgelehntem unauthentifiziertem Request, authentifiziertem HAE-v2-Import und idempotentem Reimport erfolgreich.
- Statisch/isoliert und in Linux/Docker getestet; reale Health-Auto-Export-/Home-Assistant-/iPhone-Übertragung muss lokal verifiziert werden.

## v0.2.5 – 2026-08-29

- Bestzeiten im Fortschritt-Bereich sichtbar gemacht, inklusive Quelle, Datum und aufklappbarer vollständiger Übersicht.
- Prognosekarten markieren Verbesserungen gegenüber bestätigten Bestzeiten und erklären beim Halbmarathon den verwendeten Leistungsanker.
- Mobile Bottom-Navigation kompakter gestaltet, ohne den iPhone-Safe-Area-Schutz vollständig zu entfernen.
- Progressionssignal ergänzt: kontinuierliche Trainingsentwicklung seit einer bestätigten Bestzeit kann bei ausreichend belastbarer 8-Wochen-Historie einen begrenzten Prognosefortschritt stützen; reine verstrichene Zeit erzeugt keine Verbesserung.
- Keine Datenbankschemamigration; bestehende Daten und v0.2.4-Leistungsanker bleiben erhalten.
- Validierung: Python-Compilecheck, JavaScript-Syntaxchecks, vollständige Regression, 16-Wochen-Marathonsimulation, neun randomisierte Läuferprofile, Docker-Build und Docker-Runtime-Smoke-Test erfolgreich.

## v0.2.4 – 2026-08-29

- Manuelle Bestzeiten bleiben harte Leistungsanker; Apple-Health-Läufe der letzten 24 Monate werden zusätzlich auf standarddistanznahe Bestleistungen für 5 km, 10 km, Halbmarathon und Marathon geprüft.
- Kleine Distanzabweichungen werden konservativ mit dem bestehenden Riegel-Modell normalisiert. Automatische Bestzeiten ersetzen ausschließlich automatisch erzeugte Einträge und niemals manuelle/Race-/Time-Trial-Marken.
- Prognoseengine berücksichtigt Qualität, Aktualität und Extrapolationsdistanz der Leistungsanker und kann jüngere, belastbare Trainingsleistung gegen ältere Bestzeiten abwägen.
- Neue APIs für Bestzeitenanzeige und explizite Apple-Health-Bestzeit-Synchronisation.
- Keine Datenbankschemamigration; bestehende Apple-Health-, Trainings- und Nutzerdaten bleiben erhalten.

## v0.2.2 – 2026-08-29

- Produktionsnahen Frontend-Auslieferungsfehler behoben: Der FastAPI-/Starlette-Mount `/assets` zeigte auf `static/` statt auf das tatsächliche Verzeichnis `static/assets/`. Dadurch wurden die v0.2-Erweiterungen im realen Add-on mit HTTP 404 beantwortet, während die Basis-UI weiter funktionierte.
- Dadurch werden **mehrere A-/B-Rennen** unter Einstellungen und **Planungsaggressivität Konservativ / Moderat / Aggressiv** nun tatsächlich im Home-Assistant-Frontend ausgeliefert.
- Bestehende v0.1.9-Styles unter `assets/bugfix.css` bleiben durch einen kompatiblen Asset-Pfad erhalten.
- Alle relevanten Frontend-Assets sind mit `?v=0.2.2` versioniert; der PWA-Cache wurde auf `laufapp-v0.2.2` erhöht.
- Frontend-Antworten erhalten `Cache-Control: no-store, max-age=0`, damit Home-Assistant-/iOS-WebViews nach Add-on-Updates keinen veralteten App-Shell-Stand weiterverwenden.
- Neuer v0.2.2-Entry-Point korrigiert ausschließlich Version und statische Auslieferung und übernimmt die getestete v0.2.1-API-/Trainingslogik unverändert.
- Docker-Runtime-Smoke-Test erweitert: Im gestarteten Container müssen `v020.js` und `v020_science.js` per HTTP erreichbar sein; A-/B-Rennbegriffe, die drei Aggressivitätsstufen, `/api/v2/races` und `/api/settings` werden explizit geprüft.
- Keine Datenbankschemamigration; bestehende Health-Daten, Läufe, Schuhe, Rennen, Trainingsplan und Coach-Daten bleiben unverändert.
- Validierung: Python-Compilecheck erfolgreich, JavaScript-Syntaxchecks erfolgreich, **82/82 Pytests**, 16-Wochen-Marathonsimulation erfolgreich, neun randomisierte Läuferprofile erfolgreich, Docker-Build und erweiterter Docker-Runtime-Smoke-Test erfolgreich.
- Statisch/isoliert sowie im Linux-/Docker-CI getestet; Home-Assistant-/Nabu-Casa-/iPhone-Darstellung muss nach Installation auf dem Beelink real bestätigt werden.

## v0.2.1 – 2026-08-29

- Inkonsistenz zwischen Planbasis-Wochenziel und tatsächlich erzeugten Wochenkilometern behoben: Ein nachgelagerter Longrun-Anteils-Guardrail konnte den fertigen Plan bislang unter das zuvor berechnete Wochenziel drücken, ohne die entfernten Kilometer zurückzuverteilen.
- Die normale 45-%-Longrun-Anteilsorientierung ist bei vollständig automatisch erzeugten Zukunftswochen wieder ein Belastungs-Guardrail statt eines zweiten pauschalen harten Caps. Reale verträgliche Longrun-Historie und `max_long_run_km` bleiben maßgeblich.
- Ein bewusst strengerer Longrun-Anteil des Nutzers bleibt bindend. Muss ein Guardrail in einer gemischten/geschützten Woche Distanz entfernen, werden freie Kilometer nur auf flexible zukünftige Easy Runs verteilt, soweit sinnvoll.
- Planbasis-Bezeichnungen präzisiert: **Trainingsbasis** statt „Aktueller Umfang“ und **Wochenziel** statt „Geplant“.
- **Planungsaggressivität** mit drei Stufen ergänzt: Konservativ (`gradual`), Moderat (`steady`, Standard) und Aggressiv (`progressive`). Die Stufe steuert die bestehende deterministische Blockprogression; Wochen-/Longrun-Limits, Recovery/Readiness, Qualitätsbudget, Deload und Taper bleiben in allen Stufen bindend.
- Regressionstests bilden explizit einen Fall mit ca. 60,9 km etablierter Basis, ca. 63–64 km Wochenziel, 32-km-Longrun-Historie und Nutzerobergrenze ab und prüfen außerdem die Reihenfolge Konservativ < Moderat < Aggressiv bei weiterhin bindenden Limits.
- Validierung: Python-Compilecheck, JavaScript-Syntax, **82/82 Pytests**, 16-Wochen-Marathonsimulation, neun randomisierte Läuferprofile, Docker-Build und Docker-Runtime-Smoke-Test erfolgreich.
- Keine Datenbankschemamigration.

## v0.2.0 – 2026-08-29

- Mehrere zukünftige Wettkämpfe können unter **Einstellungen → Rennen** gepflegt, bearbeitet und gelöscht werden. Bestehende v0.1.9-Wettkämpfe werden kompatibel als A-Rennen behandelt.
- **A-Rennen** steuern den Trainingsblock vollständig; das jeweils nächste zukünftige A-Rennen ist der Planfokus, nach dessen Rennwoche übernimmt automatisch das nächste A-Rennen.
- **B-Rennen** lösen keinen Taper und keine Änderung der vorherigen Trainingswochen aus. In ihrer Rennwoche ersetzen sie ausschließlich den Longrun; die übrigen Trainingseinheiten bleiben in einer normalen konfliktfreien Woche unverändert.
- Jedes Rennen besitzt eine eigene Zielzeit. Direkt darunter zeigt Laufapp dezent die datenbasierte aktuelle Zeitprognose inklusive Prognosebereich an; die Empfehlung kann optional als Ziel übernommen werden.
- Trainingsumfang erhält eine echte rennrelative Blockprogression: aufeinanderfolgende Build-/Specific-Belastungswochen können innerhalb eines Blocks ansteigen, Recovery, Nutzerobergrenzen, Detraining und Taper bleiben harte Gegenbedingungen.
- Neue wissenschaftlich orientierte Planner-Struktur trennt **TrainingPhase**, **PhysiologicalTarget**, **WorkoutType**, **WorkoutVariant**, **TrainingLoad** und **RecoveryState**; der lokale Basistrainingsplan bleibt deterministisch und LLM-unabhängig.
- Qualitätseinheiten werden nicht mehr nach Wochentagstyp ausgewählt. Zuerst wird der physiologische Reiz bestimmt, danach wählt eine deterministische Workout-Variation-Engine eine passende Form aus Schwelle, VO₂max, Ökonomie, Marathonpace, aerober Progression oder Hügel/Kraftausdauer.
- Die Variation berücksichtigt ausdrücklich die Historie der **Qualitätseinheiten**: identische Varianten werden in den folgenden ungefähr fünf Wochen deutlich benachteiligt, ohne wahllos das physiologische Trainingsziel zu wechseln.
- Marathon-Longruns unterscheiden Easy, Progression, Fast Finish, MP-Blöcke und Deload. Distanz und Marathonpace-Anteil werden nicht regelmäßig gleichzeitig stark erhöht; 30–35-km-Longruns dürfen bei passender realer Historie die normale Longrun-Anteilsorientierung überschreiten, das explizite Nutzermaximum bleibt hart.
- **Qualitätsbudget korrigiert:** ein intensiver Longrun zählt als Qualitätsreiz. Bei `Qualitätseinheiten = 1` wird der andere strukturierte Lauf nur als kleine Ökonomie-/Aktivierungseinheit dosiert statt als zweiter harter Schwellen-/VO₂max-Reiz.
- **Goal Marathon Pace** und **Current Estimated Marathon Pace** werden getrennt; Trainings-Marathonpace folgt primär dem aktuell gestützten Leistungsniveau statt blind einer ambitionierten Wunschzeit.
- Intensitätsverteilung wird rollierend über vier Wochen als Planungsmodell bewertet. Der Marathonplan bleibt klar niedrigintensiv dominiert; Prozentbereiche sind Orientierungen und keine starren wissenschaftlichen Grenzwerte.
- Readiness kombiniert persönliche HRV-/Ruhepuls-Baselines, Schlaf, subjektive Erholung, Beine, RPE, Beschwerden und – soweit vorhanden – Laufreaktionen. Ein einzelner HRV-Wert kann keine automatische harte Planentscheidung auslösen.
- Nach absolvierten Einheiten können RPE, Beine, Schmerzen und subjektive Erholung erfasst werden. Schlechte wie auch besonders gute Belastungsverträglichkeit erzeugt höchstens einen **bestätigungspflichtigen** Coach-/Planvorschlag; die App ändert zukünftige Einheiten nicht ungefragt.
- Qualitätseinheiten und besondere Longruns speichern **„Warum diese Einheit?“**, physiologisches Ziel, Workoutform und geschätzte Belastung für die Wochen-/Detailansicht.
- Der validierte 16-Wochen-Simulator prüft Periodisierung, Workoutvariation, Deloads, MP-Longruns, Longrun-Distanz-vs.-Intensität, begrenzte VO₂max-Rolle, Taper, rollierende Intensitätsverteilung und den vollständigen 42,195-km-Zielmarathon.
- Zusätzlich simuliert die CI **neun reproduzierbar randomisierte Läuferprofile** von etwa 25 bis 100 km etablierter Wochenlast, 3–7 Lauftagen und 1–3 Qualitätseinheiten mit variierenden Leistungsständen, Nutzerlimits, ambitionierten Zielzeiten, Detraining und B-Rennen. Diese Tests haben den oben genannten Qualitätsbudget-Fehler aufgedeckt und sichern den Fix dauerhaft ab.
- Absolvierte, mit einem realen Lauf verknüpfte Einheiten können direkt aus der Wochenansicht einem Schuh zugeordnet werden. Die vorhandene `runs.shoe_id`-Zuordnung wird verwendet, sodass die Kilometerbilanz des Schuhs sofort mit dem real gelaufenen Umfang steigt. Die bestehende Zuordnung im Fortschritt-Tab bleibt erhalten.
- Keine neue Datenbankschemaversion nötig: A/B-Klassifikation und subjektive Feedbackdaten werden kompatibel in bestehenden persistenten Strukturen gespeichert; vorhandene Läufe, Health-Daten, Schuhe, Trainingspläne und manuelle Änderungen bleiben erhalten.
- Home-Assistant-Ingress, `ingress_stream`, persistente SQLite-Daten und die v0.1.9-Schutzmechanismen für manuelle/absolvierte Workouts bleiben erhalten.
- Validierung des finalen Branch-Stands: Python-Compilecheck erfolgreich, JavaScript-Syntaxchecks erfolgreich, **78/78 Pytests**, 16-Wochen-Marathonsimulation erfolgreich, 9-Profil-Randomsimulation erfolgreich, Home-Assistant-Docker-Build erfolgreich und Docker-Runtime-Smoke-Test erfolgreich.
- Ausführliche Evidenz-/Algorithmusdokumentation: `TRAINING_ENGINE.md`. Das alternierende Longrun-Distanz/MP-Prinzip und konkrete Workoutrotationen werden ausdrücklich als konservative evidenzinformierte Designableitungen, nicht als direkt bewiesene überlegene Sequenzen dokumentiert.
- Statisch/isoliert getestet; Home-Assistant-/Nabu-Casa-/iPhone-Integration muss lokal auf dem Beelink verifiziert werden.

## v0.1.9 – 2026-08-28

- „Plan neu berechnen“ aus Einstellungen funktioniert auch ohne vorher geöffneten Woche-Tab; ein `start=null` wird als aktuelle Kalenderwoche behandelt statt als 422-Fehler mit `[object Object]` im Frontend zu enden.
- Die Wochenplanung repariert eindeutig veraltete v0.1.8-Engine-Dubletten, wenn auf demselben Tag bereits eine absolvierte, verknüpfte oder manuell geschützte Einheit vorhanden ist, und erzeugt auf belegten Tagen keine zusätzliche automatische Einheit.
- Bei einer Neuberechnung berücksichtigt der automatisch erzeugte Restplan bereits geschützte Wochenkilometer. Automatische Einheiten werden bei Bedarf skaliert, statt die eingestellte Wochenobergrenze durch Addition auf absolvierte/manuelle Einheiten zu überschreiten.
- Fortschritt: Datumsbeschriftungen der Wochen stehen wieder im reservierten Bereich unter den Balken und überlagern das Diagramm nicht mehr.
- Woche: Drag-Griffe bleiben bewusst nur an geplanten, verschiebbaren Einheiten sichtbar; absolvierte/geschützte Zeilen behalten nun dennoch dieselbe Spaltenausrichtung.
- Keine Datenbankschemaänderung; Apple-Health-Daten, Läufe, Schuhe, Wettkämpfe, Einstellungen und manuelle Planänderungen bleiben erhalten.

## v0.1.8 – 2026-08-28

- Dedizierte mobile Einstellungen-Navigation mit persistenten, serverseitig validierten Planungslimits.
- Deterministische Engine unterstützt 3–7 Lauftage, 1–3 Qualitätseinheiten, automatische/manuelle Wochenobergrenze und distanzabhängige Longrun-Obergrenzen (Marathon: 35 km). Intensive Longruns verbrauchen dabei ein Qualitätsbudget.
- Planneuberechnung aus Woche entfernt und nach Einstellungen verschoben; stale Hinweis verlinkt dorthin.
- Produktionsfehler behoben: „Wochenumfang“, Longrun und Qualität vergleichen jetzt dieselbe einzelne Startwoche; zuvor wurden alle Wochen des Refresh-Fensters addiert.
- „Aktuelle Woche“ ergänzt; bestehender Request-Zähler schützt weiterhin vor verspäteten Wochenantworten.
- Additive Settings-Schlüssel benötigen keine Tabellenschema-Migration und bewahren bestehende Werte.

## v0.1.7 – 2026-08-28

- Robuste etablierte Wochenlast aus acht abgeschlossenen Wochen; Teilwoche ist nur Kontext, echter Rückgang wird separat erkannt.
- Rennrelative Build/Specific/Peak/Taper/Race-Phasen, blockbasierte Recovery und periodisierte Qualität/Marathon-Long-Runs.
- Explizite Planfrische und transaktionale Neuberechnung mit Diff; kein stilles Überschreiben nach Health-Import.
- Schema 4 schützt manuell verschobene/getauschte, Coach-geänderte, vergangene, verknüpfte und absolvierte Einheiten.
- Planbasis und Long-Run-Begründung machen die lokale, LLM-unabhängige Verschreibung nachvollziehbar.

## v0.1.6 – 2026-08-28

- Apple-Health-Diagnose trennt erwartete Ausschlüsse außerhalb des 24-Monats-Zeitraums von ungültigen Workouts und zeigt erkannte, vorhandene und neue Health-Metriken verständlich an.
- Der bestehende Uploadbereich akzeptiert ZIP und `export.xml` nun auch per Drag & Drop; Dateiauswahl und Drop verwenden dieselbe Ingress-Streaming-/Job-Pipeline.
- Optionaler, einmal bestätigter Ersatzmodus tauscht ausschließlich Apple-Health-Daten in einer Transaktion aus. Fehler rollen vollständig zurück; RPE, Notizen, Schuh und eindeutige Workout-Verknüpfungen werden anhand stabiler Apple-IDs wiederhergestellt.
- Workout-Drag & Drop erkennt nun neben der kompakten Tagesleiste auch die tatsächlich übereinander abgelegten Workout-Karten als Drop-Ziele; Backend-Move/-Swap bleibt atomar und schützt abgeschlossene/ausgefallene Einheiten.
- Wochenkilometer-Balken sind per Klick/Tap auswählbar und zeigen Zeitraum sowie Kilometer in einem dezent rot akzentuierten Overlay.
- Fortschritt ergänzt die kalendergenauen Zeiträume „Dieses Jahr“ und „Letztes Jahr“; grenzüberschreitende ISO-Wochen enthalten ausschließlich Läufe des gewählten Kalenderjahres. Lange Zeiträume beschriften die weiterhin wöchentlichen Balken sparsamer.
- Additive Schema-3-Migration speichert den Ersatzmodus eines Hintergrundjobs restartfest und erstellt vorher das bestehende integrity-geprüfte Backup.
- Statisch/isoliert getestet; Home-Assistant-Integration muss auf dem Beelink verifiziert werden.

## v0.1.5 – 2026-08-28

- Apple-Health-Workouts werden zusätzlich aus nativen `WorkoutStatistics` (Distanz, Dauer, Energie) gelesen; Endzeit dient konservativ als Dauer-Fallback.
- Persistente Importergebnisse enthalten aggregierte Lauf-, Metrik-, Sample-, Routen- und Ablehnungsdiagnosen sowie Success/Warning-Klassifikation.
- Health-Ergebnisansicht unterscheidet „0 neu“ von „0 gefunden“ und zeigt v0.1.4-Legacyfelder weiterhin.
- Wochenwechsel per Swipe, race-sicheres Rendering und Pointer-Drag am Griff; freie Tage verschieben, belegte geplante Tage tauschen atomar.
- Wochenkilometer-API und Auswahl für 1/3/6/12 Monate ohne 100-Läufe-Limit.
- Bottom-Navigation um rund 18 % vergrößert.
- Keine Schemaänderung; persistente SQLite-Daten und Ingress-Schutz bleiben unverändert.

## v0.1.4 – 2026-08-28

### Behoben
- Home Assistant Ingress streamt große Apple-Health-Uploads nun direkt zur Laufapp, statt sie vor der Weiterleitung vollständig zu puffern.
- Die bestehende Ingress-only-Zugriffskontrolle und der standardmäßig nicht veröffentlichte Webport bleiben unverändert.
- Ein statischer Regressionstest stellt sicher, dass Ingress-Streaming in der Home-Assistant-App-Konfiguration aktiviert bleibt.

## v0.1.3 – 2026-08-28

### Datenhaltung & Updates
- Explizites Datenbankschema (`PRAGMA user_version`) und versionierte Migrationen eingeführt.
- Bestehende v0.1.0–v0.1.2-Datenbanken werden additiv auf Schema 2 migriert; Läufe, Health-Daten, Schuhe, Wettkämpfe, Trainingsplan, Bestleistungen und Coach-Daten bleiben erhalten.
- Vor Schema-Migration wird eine integrity-geprüfte SQLite-Sicherung unter `/data/backups/` erzeugt.
- Bei Migrationsfehler wird der Vorzustand aus dem Backup wiederhergestellt und der App-Start bricht ab; Downgrades auf ein älteres Schema werden blockiert.
- Einmalige, integrity-geprüfte Datenbrücke über `/share/laufapp-transfer/` für den Wechsel von der bisherigen Local App zur späteren GitHub-Repository-App ergänzt. Vorhandene Repository-Daten werden niemals überschrieben.

### Apple Health
- Apple-Health-Import auf persistenten serverseitigen Hintergrundjob umgestellt.
- Nach abgeschlossenem Upload kann Browser/Home-Assistant-App geschlossen oder minimiert werden; Status bleibt persistent abrufbar.
- Ein beim App-Neustart unterbrochener Verarbeitungsjob wird beim nächsten Start erneut aufgenommen; deduplizierte Inserts und transaktionaler Health-Import verhindern Doppel-/Teildaten.
- Klare Phasen- und Prozentanzeige im Bereich **Mehr → Apple Health**.
- Fehlgeschlagene Jobs können erneut gestartet werden, solange die lokale Importdatei vorhanden ist.
- Zeitaufgelöste Laufmetriken ergänzt: Herzfrequenz, Running Speed, Running Power, Schrittlänge, vertikale Oszillation und Bodenkontaktzeit; Kadenz wird aus zeitgebundenen Step-Count-Samples abgeleitet.
- GPX-Routen werden – soweit im Apple-Export vorhanden – dem passenden Lauf zugeordnet; GPS-Punkte und Höhenprofil werden gespeichert, fehlende Höhenmeter können aus dem Profil abgeleitet werden.
- Neuer Detail-Endpunkt für Sample-Zusammenfassung und GPS-Punktzahl je Lauf.

### GitHub / Release-Prozess
- Repository-Metadaten (`repository.yaml`) für ein Home-Assistant-Custom-Repository ergänzt.
- GitHub-Actions-CI ergänzt: Python 3.13, Compilecheck, Node-Syntaxcheck, vollständige Regressionstests und Docker-Build.
- Tests sind self-contained; der v0.1.2-Migrationsfixture liegt im Repository und benötigt keinen alten lokalen Quellbaum.
- Docker-COPY-Quellen werden weiterhin statisch gegen den Build-Kontext geprüft.

### Tests
- 30 automatisierte Tests plus separater ca. 100-MB-/699k-Record-Importtest.
- 390-px- und 320-px-Renderprüfung für die neue Import-/Transfer-Oberfläche.

## v0.1.2 – 2026-08-28

### Behoben
- Home-Assistant-Cloud/Ingress-Zugriff repariert: Die Ingress-Sicherheitsprüfung erkennt nun die von Home Assistant Core gesetzten Header `X-Hass-Source: core.ingress` und `X-Ingress-Path`, statt sich auf die durch Proxy-Header umgeschriebene Client-IP zu verlassen.
- Direkter Zugriff bleibt blockiert; der Webport ist weiterhin nicht auf den Home-Assistant-Host veröffentlicht.
- Regressionstest für echten Ingress-Headerpfad, blockierten Direktzugriff und lokalen Healthcheck ergänzt.

## v0.1.1 – 2026-08-28

### Behoben
- Home-Assistant-Docker-Build repariert: `requirements.txt` liegt im Root der lokalen App und wird nun von dort in das Image kopiert.
- Neuer statischer Release-Test prüft die `COPY`-Quellen des Dockerfiles.

## v0.1.0 – 2026-08-28

Erstes funktionsfähiges privates Release mit mobile-first PWA, Heute/Woche/Fortschritt/Coach/Mehr, vier Trainingstagen, Zielzeitsteuerung, Apple-Health-Basisimport, Schuhtracking, Prognosen und bestätigungspflichtigem AI-Coach.