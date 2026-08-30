# Sicherheitskonzept – Laufapp v0.2.11

Laufapp ist eine private Home-Assistant-Anwendung. Dieses Dokument beschreibt die tatsächlich implementierten Schutzgrenzen. Es ist keine Behauptung absoluter Sicherheit; reale Home-Assistant-, Nabu-Casa-, Netzwerk- und iPhone-Integration müssen auf dem Zielsystem zusätzlich verifiziert werden.

## Netzwerk- und Vertrauensgrenzen

Die Hauptanwendung auf Port 8099 ist ausschließlich für Home Assistant Ingress vorgesehen. Der Port ist in `config.yaml` standardmäßig nicht auf den Host veröffentlicht. Uvicorn läuft mit `--no-proxy-headers`, sodass gefälschte Forwarding-Header die reale TCP-Peer-Adresse nicht überschreiben können.

Der dokumentierte Home-Assistant-Ingress-Proxy `172.30.32.2` wird direkt akzeptiert. Der in v0.2.9 ergänzte Kompatibilitätspfad akzeptiert andere Peers ausschließlich innerhalb des internen Home-Assistant-Netzes `172.30.32.0/23` und nur zusammen mit einem `X-Ingress-Path` unter `/api/hassio_ingress/` sowie einem authentifizierten Ingress-Marker (`X-Remote-User-Id` oder `X-Hass-Source: core.ingress`). Loopback ist ausschließlich für `/api/health` zugelassen. Externe Clients bleiben auch mit gefälschten Ingress-/Forwarding-Headern gesperrt.

Der Health-Auto-Export-Gateway läuft getrennt auf Port 8100. OpenAPI-/Swagger-/ReDoc-Endpunkte sind deaktiviert. Port 8100 wird **gar nicht gestartet**, solange kein ausreichend starker Sync-Token konfiguriert ist. Auch Port 8100 ist in `config.yaml` standardmäßig nicht auf den Home-Assistant-Host veröffentlicht.

`POST /home-assistant-relay` bleibt der dedizierte interne Zielpfad. v0.2.11 ergänzt davor die Home-Assistant-Custom-Integration `laufapp_hae_relay`. Health Auto Export sendet über HTTPS an `https://<remote-id>.ui.nabu.casa/api/webhook/<secret-id>`. Die Custom Integration liest den Request-Body direkt und leitet ihn ohne Jinja-/Automation-Serialisierung über das Supervisor-interne App-Netz an `http://c87ed7df-laufapp:8100/home-assistant-relay` weiter. Der interne HTTP-Hop verlässt den Home-Assistant-Host nicht und verlangt zusätzlich den separaten starken `X-Laufapp-Token`.

**Ports 8099 und 8100 nicht ins Internet weiterleiten.** Für den vorgesehenen Nabu-Casa-Betrieb ist keine Router-Portfreigabe und keine Veröffentlichung von 8100 auf dem Home-Assistant-Host erforderlich.

## Nabu Casa / Webhook-Relay

- Der öffentliche Endpunkt ist der normale Nabu-Casa-Remote-UI-HTTPS-Endpunkt plus die geheime Home-Assistant-Webhook-ID.
- Die zufällige Webhook-ID/URL ist ein Geheimnis und wird weder im Repository noch in der Laufapp-Konfiguration hinterlegt.
- Das Webhook-Geheimnis ist **nicht** der Laufapp-Token. Home Assistant ergänzt `X-Laufapp-Token` erst auf dem internen Relay-Hop.
- Der öffentliche Webhook akzeptiert ausschließlich POST. Die Custom Integration akzeptiert nur `application/json`.
- Der Body wird direkt gelesen und nicht in ein Home-Assistant-Template gerendert. Damit greift nicht die beobachtete 262144-Zeichen-Ausgabegrenze der bisherigen `trigger.json | to_json`-Automation.
- Die Custom Integration begrenzt den Request auf 16 MiB. Das interne Laufapp-Gateway erzwingt dieselbe Größenordnung und weitere Mengen-/Timeoutgrenzen erneut.
- Das interne Ziel ist im Code fest auf `http://c87ed7df-laufapp:8100/home-assistant-relay` gesetzt. Der Relay kann nicht als frei konfigurierbarer HTTP-Proxy missbraucht werden.
- Der Laufapp-Relay-Endpunkt akzeptiert bewusst keinen Bearer-Token; der dokumentierte interne Vertrag verwendet ausschließlich `X-Laufapp-Token`.
- Home Assistant adressiert Laufapp über den Supervisor-internen DNS-Namen; der Host-Port 8100 bleibt deaktiviert.
- Die Custom Integration schreibt weder Request-Body noch Webhook-ID noch Token in normale Logs.
- Für HAE wird **Previous 7 Days / Letzte 7 Tage** statt `Since Last Sync` empfohlen. Wiederholte Übertragung ist durch die bestehende Lauf-/Sample-/GPS-/Health-Metric-Deduplizierung idempotent.

Der alte v0.2.10-Automations-/`rest_command`-Pfad bleibt ausschließlich als Legacy-/Diagnosebeispiel im Repository. Detaillierte HAE-Workout-Payloads sollen ihn nicht verwenden, weil die Home-Assistant-Template-Ausgabe auf 262144 Zeichen begrenzt ist.

## Health Auto Export

- eigener, von OpenAI- und Home-Assistant-Zugangsdaten getrennter Token
- mindestens 48 Zeichen, höchstens 256 Zeichen, keine Leerzeichen, Mindestdiversität; empfohlen wird ein kryptografisch zufälliger Token
- timing-resistenter Vergleich über `hmac.compare_digest`
- Authentifizierung erfolgt **vor** dem Lesen des Request-Bodys im Laufapp-Gateway
- nur JSON-Content-Type wird akzeptiert
- maximal 16 MiB pro Request; Limit wird bereits während des Streamings erzwungen
- maximales Body-Zeitfenster 120 Sekunden als Schutz gegen sehr langsame Requests
- Limits für Workoutzahl, Messpunkte, GPS-Punkte und Health-Metriken
- Workout-ID-Kollisionen mit abweichendem Start, Distanz oder Dauer werden abgelehnt
- Reimporte und Cross-Source-Übergänge vom klassischen Apple-Health-Import werden dedupliziert
- die Gateway-Antwort enthält keine Prognosen, Trainingsdaten oder Versionsinformationen
- Gateway-Antworten erhalten `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` und `Referrer-Policy: no-referrer`; der Uvicorn-Server-Header ist deaktiviert
- die Parallelität des Gateways ist begrenzt

## Apple-Health-ZIP/XML-Import

Der klassische ZIP/XML-Import bleibt als Historien- und Backup-Pfad erhalten und ist nur hinter Home Assistant Ingress erreichbar.

- Upload wird gestreamt und ist auf 2 GiB begrenzt
- ZIP wird nicht per `extractall` entpackt; `export.xml` und GPX-Dateien werden direkt aus dem Archiv gestreamt
- maximal 20.000 ZIP-Einträge
- genau eine `export.xml` erforderlich
- verschlüsselte ZIP-Einträge werden abgelehnt
- entpackte `export.xml` maximal 8 GiB
- Kompressionsverhältnis für `export.xml` und GPX wird begrenzt, um Dekompressionsbomben abzuwehren
- GPX-Gesamt- und Einzeldateigrößen werden begrenzt
- maximal 250.000 GPS-Punkte pro Route
- GPS-Koordinaten und Höhenwerte werden plausibilisiert
- XML/GPX wird mit `defusedxml` geparst; Entity Expansion und externe XML-Referenzen sind gesperrt
- Health-Daten werden transaktional importiert; Parserfehler hinterlassen keinen halb importierten Datensatz
- wiederholte Exporte werden über externe IDs/Fingerprints dedupliziert

## Datenhaltung und Secrets

Trainingsdaten, Wettkämpfe, Schuhe, Health-Metriken, Laufzeitreihen, GPS-Punkte, Plan und Chat-Historie liegen in SQLite unter `/data`. Der Home-Assistant-App-Code liegt getrennt im Container-Image. Vor Datenbankschemamigrationen wird ein integrity-geprüftes Backup erzeugt; Downgrades auf ein nicht unterstütztes älteres Schema werden blockiert.

`openai_api_key` und `health_auto_export_token` sind Home-Assistant-Passwortoptionen und werden nicht durch die Laufapp-API an das Frontend ausgegeben. Für den Home-Assistant-Relay wird derselbe HAE-Token zusätzlich als Home-Assistant-Secret referenziert; er darf nicht im Klartext in `configuration.yaml` oder Repository eingecheckt werden. Die öffentliche Webhook-ID wird separat als Secret gespeichert. Dateierzeugung erfolgt mit restriktivem `umask 077`.

## OpenAI / KI

Der OpenAI-Key bleibt serverseitig. Der Coach erhält nur den für die konkrete Analyse zusammengestellten Trainingskontext. Screenshots werden nur nach expliziter Nutzeraktion an die OpenAI API gesendet und nicht dauerhaft als Bild gespeichert. KI-Vorschläge können den Trainingsplan nicht eigenständig verändern: Änderungen werden serverseitig validiert und müssen vom Nutzer ausdrücklich bestätigt werden.

## Browser / XSS

Die dynamischen Frontendpfade wurden auf Stored/Reflected XSS geprüft. Nutzer- und Modelldaten wie Coach-Antworten, Rennnamen, Notizen, Leistungslabels und Quellen werden vor HTML-Einfügung escaped. Externe Quellenlinks werden nur für `http:`/`https:` akzeptiert und mit `noopener noreferrer` geöffnet. Im geprüften Rendering-Pfad wurde keine offene Stored-XSS-Lücke gefunden.

## Supply Chain und CI

Direkte Runtime-Abhängigkeiten sind auf geprüfte Versionen gepinnt. `pip-audit` blockiert Releases bei bekannten Python-Abhängigkeitsschwachstellen. Der FastAPI-/Starlette-Stack wurde im Security-Review auf gepatchte Versionen aktualisiert. Zusätzlich läuft Bandit über den Python-Code; nur exakt dokumentierte Legacy-Findings mit geprüfter Nicht-Sicherheitsbedeutung dürfen den Review-Gate passieren, neue Medium/High-Findings blockieren die CI.

Die Home-Assistant-Custom-Integration fügt keine externen Python-Abhängigkeiten hinzu. Sie verwendet ausschließlich Home-Assistant-/aiohttp-APIs, die im Home-Assistant-Core-Prozess bereits vorhanden sind.

GitHub-Actions werden nicht über bewegliche Major-Tags geladen, sondern auf geprüfte Commit-SHAs gepinnt. Workflow-Rechte sind auf `contents: read` begrenzt.

## Bewusst verbleibende Risiken

Der Container läuft weiterhin im Home-Assistant-App-Modell mit den dort nötigen Dateirechten und besitzt für den bestehenden Repository-Transferpfad `/share:rw`. Eine Umstellung auf einen strikt nicht privilegierten Container beziehungsweise Entfernung des Share-Mounts würde das Home-Assistant-Persistenz-/Migrationsverhalten beeinflussen und wird ohne realen Supervisor-Test nicht vorgenommen. Diese Punkte sind lokale Host-/Container-Risiken, keine Begründung für eine öffentliche Portfreigabe.

Ein gültiger Health-Auto-Export-Token erlaubt weiterhin das **Schreiben** plausibler Health-Daten. Deshalb muss er wie ein Passwort behandelt und bei Verdacht sofort rotiert werden. Der Gateway ist bewusst write-only, damit derselbe Token nicht zum Auslesen persönlicher Laufdaten genutzt werden kann.

Ein gültiger öffentlicher Webhook-Link kann den Home-Assistant-Relay auslösen. Der zweite Laufapp-Token verhindert zwar direkten Schreibzugriff auf den Laufapp-Gateway außerhalb Home Assistants, dennoch muss auch die Webhook-ID geheim bleiben, um unautorisierte Relay-Last und Schreibversuche zu vermeiden.

Die Custom Integration läuft im Home-Assistant-Core-Prozess. Ein Fehler in diesem Code kann daher den Home-Assistant-Prozess belasten. Der Code ist bewusst klein gehalten, akzeptiert nur POST/JSON, begrenzt den Body, besitzt ein festes internes Ziel und einen Zeitrahmen für die Weiterleitung. Reale Langzeitbelastung und iPhone-Hintergrundverhalten müssen trotzdem auf dem Zielsystem beobachtet werden.

## Release-Grenze

Automatisiert geprüft werden Compile/Syntax einschließlich Custom Integration, Regressionstests über den aktuellen Entry-Point, ein isolierter >262144-Zeichen-Relaytest, Body-/Content-Type-/Secret-Grenzen, Trainingssimulationen, Dependency-Audit, Bandit-Gate, Docker-Build, authentifizierter und unauthentifizierter Health-Auto-Export, idempotenter Reimport, der interne Relay-Pfad samt Bearer-Negativtest sowie die Home-Assistant-Ingress-Netzsimulation und externe Header-Spoofing-Abwehr.

Statisch/isoliert und in Linux/Docker getestet. Die echte Home-Assistant-OS-/Custom-Integration-/Nabu-Casa-Remote-UI-/Health-Auto-Export-iPhone-Kette muss nach Installation lokal verifiziert werden.