# Sicherheitskonzept – Laufapp v0.2.13

Laufapp ist eine private Home-Assistant-Anwendung. Dieses Dokument beschreibt die tatsächlich implementierten Schutzgrenzen. Es ist keine Behauptung absoluter Sicherheit; reale Home-Assistant-, Nabu-Casa-, Netzwerk-, Router- und iPhone-Einstellungen müssen auf dem Zielsystem zusätzlich verifiziert werden.

## Netzwerk- und Vertrauensgrenzen

Die Hauptanwendung auf Port 8099 ist ausschließlich für Home Assistant Ingress vorgesehen. Der Port ist in `config.yaml` nicht auf den Host veröffentlicht. Uvicorn läuft mit `--no-proxy-headers`, sodass gefälschte Forwarding-Header die reale TCP-Peer-Adresse nicht überschreiben können.

Der dokumentierte Home-Assistant-Ingress-Proxy `172.30.32.2` wird direkt akzeptiert. Der Kompatibilitätspfad akzeptiert andere Peers ausschließlich innerhalb des internen Home-Assistant-Netzes `172.30.32.0/23` und nur zusammen mit einem `X-Ingress-Path` unter `/api/hassio_ingress/` sowie einem authentifizierten Ingress-Marker (`X-Remote-User-Id` oder `X-Hass-Source: core.ingress`). Loopback ist ausschließlich für `/api/health` zugelassen. Externe Clients bleiben auch mit gefälschten Ingress-/Forwarding-Headern gesperrt.

Der Health-Auto-Export-Gateway läuft getrennt auf Port 8100. OpenAPI-/Swagger-/ReDoc-Endpunkte sind deaktiviert. Port 8100 wird gar nicht gestartet, solange kein ausreichend starker Sync-Token konfiguriert ist. Auch Port 8100 ist nicht auf den Home-Assistant-Host veröffentlicht.

`POST /home-assistant-relay` bleibt der dedizierte interne Zielpfad. Health Auto Export sendet über HTTPS an `https://<remote-id>.ui.nabu.casa/api/webhook/<secret-id>`. Die Custom Integration liest den Request-Body direkt und leitet ihn über das Supervisor-interne App-Netz an `http://c87ed7df-laufapp:8100/home-assistant-relay` weiter. Der interne HTTP-Hop verlässt den Home-Assistant-Host nicht und verlangt zusätzlich den separaten starken `X-Laufapp-Token`.

**Ports 8099 und 8100 nicht ins Internet weiterleiten.** Für den vorgesehenen Nabu-Casa-Betrieb ist keine Router-Portfreigabe erforderlich.

## Minimale Home-Assistant-Rechte

Der früher für den einmaligen Wechsel von der lokalen App zum GitHub-Repository benötigte Mount `share:rw` wurde in v0.2.13 aus `config.yaml` entfernt. Die produktive Laufapp besitzt damit keinen Zugriff mehr auf Home Assistants `/share`-Bereich. Der öffentliche Vorbereitungsendpunkt `/api/system/prepare-repository-transfer` wird nicht mehr registriert.

Die interne historische Transfer-/Adoptionslogik verbleibt ausschließlich als Alt-/Recovery-Kompatibilität im Quellcode. Ohne `/share`-Mount und ohne Vorbereitungsendpunkt ist sie im normalen Betrieb inaktiv.

## Nabu Casa / Webhook-Relay

- Der öffentliche Endpunkt ist der Nabu-Casa-Remote-UI-HTTPS-Endpunkt plus die geheime Home-Assistant-Webhook-ID.
- Die zufällige Webhook-ID/URL ist ein Geheimnis und wird weder im Repository noch in der Laufapp-Konfiguration hinterlegt.
- Das Webhook-Geheimnis ist nicht der Laufapp-Token. Home Assistant ergänzt `X-Laufapp-Token` erst auf dem internen Relay-Hop.
- Der öffentliche Webhook akzeptiert ausschließlich POST und `application/json`.
- Der Body wird direkt gelesen und nicht in ein Home-Assistant-Template gerendert.
- Requestgröße: maximal 16 MiB.
- Body-Read-Timeout: 120 Sekunden gegen Slow-Request-/Trickle-Angriffe.
- Rate-Limit: maximal 12 akzeptierte Requests pro 60 Sekunden pro laufender Integration.
- Parallelität: maximal drei gleichzeitig laufende Forwardings; weitere Requests werden nach kurzem Wartefenster mit HTTP 429 abgewiesen.
- Das interne Ziel ist fest auf `http://c87ed7df-laufapp:8100/home-assistant-relay` gesetzt; kein nutzergesteuerter SSRF-Zielhost.
- Der Laufapp-Relay-Endpunkt akzeptiert bewusst keinen Bearer-Token; der interne Vertrag verwendet ausschließlich `X-Laufapp-Token`.
- Die Custom Integration schreibt weder Request-Body noch Webhook-ID noch Token in normale Logs.
- Für HAE wird **Previous 7 Days / Letzte 7 Tage** empfohlen. Wiederholte Übertragung ist durch Deduplizierung idempotent.

Die alten Automation-/Jinja-/`rest_command`-Relay-Beispiele wurden in v0.2.13 aus dem Repository entfernt. Der produktive Weg ist nur noch die Custom Integration.

## Health Auto Export

- eigener, von OpenAI- und Home-Assistant-Zugangsdaten getrennter Token
- mindestens 48 Zeichen, höchstens 256 Zeichen, keine Leerzeichen, Mindestdiversität; kryptografisch zufällig empfohlen
- timing-resistenter Vergleich über `hmac.compare_digest`
- Authentifizierung vor dem Lesen des Request-Bodys im Laufapp-Gateway
- nur JSON-Content-Type
- maximal 16 MiB pro Request; Streaminglimit
- maximales Body-Zeitfenster 120 Sekunden im Gateway
- Limits für Workoutzahl, Messpunkte, GPS-Punkte und Health-Metriken
- Workout-ID-Kollisionen mit abweichendem Start, Distanz oder Dauer werden abgelehnt
- Reimporte und Cross-Source-Übergänge werden dedupliziert
- Gateway-Antwort enthält keine Prognosen, Trainingsdaten oder Versionsinformationen
- `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`; Server-Header deaktiviert
- Gateway-Parallelität zusätzlich über Uvicorn begrenzt

## Apple-Health-ZIP/XML-Import

Der klassische ZIP/XML-Import bleibt als Historien- und Backup-Pfad erhalten und ist nur hinter Home Assistant Ingress erreichbar.

- Upload wird gestreamt und ist auf 2 GiB begrenzt
- ZIP wird nicht per `extractall` entpackt; `export.xml` und GPX werden direkt aus dem Archiv gestreamt
- maximal 20.000 ZIP-Einträge
- genau eine `export.xml` erforderlich
- verschlüsselte ZIP-Einträge werden abgelehnt
- entpackte `export.xml` maximal 8 GiB
- begrenztes Kompressionsverhältnis gegen Dekompressionsbomben
- GPX-Gesamt- und Einzeldateigrößen begrenzt
- maximal 250.000 GPS-Punkte pro Route
- GPS-Koordinaten/Höhen plausibilisiert
- XML/GPX mit `defusedxml`; Entity Expansion/externe XML-Referenzen gesperrt
- transaktionaler Import; Parserfehler hinterlassen keinen halben Datensatz
- Deduplizierung über externe IDs/Fingerprints

## Browser / API

Zusätzlich zur Ingress-Vertrauensgrenze setzt v0.2.13 folgende Defense-in-Depth-Maßnahmen:

- Schreibmethoden `POST`, `PUT`, `PATCH`, `DELETE` werden abgewiesen, wenn ein moderner Browser sie explizit als `Sec-Fetch-Site: cross-site` kennzeichnet.
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`
- restriktive `Permissions-Policy` für Kamera, Mikrofon, Geolocation, Payment und USB
- Content-Security-Policy: Ressourcen/Requests grundsätzlich nur vom eigenen Origin; `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`; Inline-Styles bleiben wegen der bestehenden UI nötig.
- Der Coach-History-Endpunkt akzeptiert nur Limits von 1 bis 200 Einträgen.
- Andere Listen-/Upload-Endpunkte besitzen bereits serverseitige Mengen- bzw. Größenlimits.

Die dynamischen Frontendpfade wurden auf Stored/Reflected XSS geprüft. Nutzer- und Modelldaten wie Coach-Antworten, Rennnamen, Notizen, Leistungslabels und Quellen werden vor HTML-Einfügung escaped. Externe Quellenlinks werden nur für `http:`/`https:` akzeptiert und mit `noopener noreferrer` geöffnet.

## Datenhaltung und Secrets

Trainingsdaten, Wettkämpfe, Schuhe, Health-Metriken, Laufzeitreihen, GPS-Punkte, Plan und Chat-Historie liegen in SQLite unter `/data`. Der App-Code liegt getrennt im Container-Image. Vor Datenbankschemamigrationen wird ein integrity-geprüftes Backup erzeugt; Downgrades auf nicht unterstützte ältere Schemas werden blockiert.

`openai_api_key` und `health_auto_export_token` sind Home-Assistant-Passwortoptionen und werden nicht über die Laufapp-API an das Frontend ausgegeben. Für den Home-Assistant-Relay wird derselbe HAE-Token als Home-Assistant-Secret referenziert; er darf nicht im Klartext in Repository/YAML eingecheckt werden. Die öffentliche Webhook-ID wird separat als Secret gespeichert. Dateierzeugung erfolgt mit restriktivem `umask 077`.

`.gitignore` schließt lokale SQLite-Daten, `options.json`, `secrets.yaml`, `.env`, ZIP-Exporte und Finder-Metadaten aus. Zusätzlich scannt die Security-CI die erreichbare Git-Historie auf typische reale Secret-Formate.

## OpenAI / KI

Der OpenAI-Key bleibt serverseitig und wird nie an den Browser ausgeliefert. Der Coach erhält nur den für die konkrete Anfrage zusammengestellten Trainingskontext. Bei der Analyse eines einzelnen Laufs werden ausschließlich lokal abgeleitete Kennwerte, die verknüpfte Planeinheit, kompakte Vergleichswerte, Wochenlast und relevante Recovery-Aggregate übertragen; GPS-Rohkoordinaten und die vollständige Health-Datenbank werden nicht übertragen. Screenshots werden nur nach expliziter Nutzeraktion an die OpenAI API gesendet und nicht dauerhaft als Bild gespeichert.

Alle Responses-Aufrufe setzen `store=false`, damit kein abrufbares OpenAI-Response-Objekt als Anwendungszustand gespeichert wird. Das ersetzt keine Zero-Data-Retention-Vereinbarung: Standardmäßige Abuse-Monitoring-Logs können abhängig von den Datenkontrollen des OpenAI-Projekts bis zu 30 Tage bestehen. Strukturierte Antworten werden gegen ein festes JSON-Schema angefordert; Laufnotizen und sonstige eingebettete Texte sind im Prompt ausdrücklich unvertraute Daten und dürfen keine Systemanweisungen überschreiben.

KI-Vorschläge können den Trainingsplan nicht eigenständig verändern: Änderungen werden serverseitig gegen konservative Grenzen validiert, als offen gespeichert und müssen ausdrücklich bestätigt werden. Ein identischer offener Vorschlag wird nicht erneut angelegt.

## Supply Chain und CI

Direkte Runtime-Abhängigkeiten sind gepinnt. `pip check` prüft die installierte Abhängigkeitskonsistenz; `pip-audit` blockiert bei bekannten Python-Abhängigkeitsschwachstellen. Bandit läuft über Backend und Custom Integration; neue Medium/High-Findings blockieren den Security-Gate.

Die Home-Assistant-Custom-Integration fügt keine externen Python-Abhängigkeiten hinzu und nutzt Home-Assistant-/aiohttp-APIs aus Core.

GitHub-Actions werden auf konkrete Commit-SHAs gepinnt. Workflow-Rechte bleiben `contents: read`. Für den History-Scan wird die vollständige Historie eingelesen und auf typische OpenAI-/GitHub-Tokenpräfixe, JWTs, Private Keys und reale Nabu-Casa-Webhook-URLs geprüft.

## Bewusst verbleibende Risiken

Ein gültiger Health-Auto-Export-Token erlaubt weiterhin das **Schreiben** plausibler Health-Daten. Er muss wie ein Passwort behandelt und bei Verdacht rotiert werden. Der Gateway ist write-only, damit derselbe Token nicht zum Auslesen persönlicher Laufdaten genutzt werden kann.

Ein gültiger öffentlicher Webhook-Link kann Home Assistant weiterhin erreichen. Rate-/Parallelitäts-/Größen-/Timeoutgrenzen reduzieren Missbrauchsfolgen, ersetzen aber nicht die Geheimhaltung der Webhook-ID. Bei Verdacht auf Leak muss die Webhook-ID rotiert werden.

Die Custom Integration läuft im Home-Assistant-Core-Prozess. Ein Fehler in diesem kleinen Code kann Core belasten. Deshalb sind Größe, Zeit, Rate, Parallelität, Methode, Content-Type und Zieladresse begrenzt. Reale Langzeitbelastung und iPhone-Hintergrundverhalten müssen trotzdem auf dem Zielsystem beobachtet werden.

Die Laufapp kann nicht aus dem Repository heraus verifizieren, ob am Router Port 8123/8099/8100 weitergeleitet wird, ob alle Home-Assistant-Konten MFA verwenden, ob alte Benutzerkonten existieren oder ob Home Assistant selbst aktuell gepatcht ist. Diese Host-/Account-Punkte müssen auf dem realen System geprüft werden.

## Release-Grenze

Automatisiert geprüft werden Compile/Syntax einschließlich Custom Integration, Regressionstests über den aktuellen Entry-Point, realistische HAE-Workouts, >262144-Zeichen-Relay, Body-/Content-Type-/Secret-/Rate-/Slow-Body-Grenzen, Trainingssimulationen, `pip check`, Dependency-Audit, Git-History-Secret-Scan, Bandit, Docker-Build, authentifizierter/unauthentifizierter HAE-Import, idempotenter Reimport, interner Relay-Pfad sowie Home-Assistant-Ingress-Netzsimulation und externe Header-Spoofing-Abwehr.

Statisch/isoliert und in Linux/Docker getestet. Die echte Home-Assistant-OS-/Custom-Integration-/Nabu-Casa-Remote-UI-/Health-Auto-Export-iPhone-Kette muss nach Installation lokal verifiziert werden.
