# Sicherheitskonzept – Laufapp v0.2.7

Laufapp ist eine private Home-Assistant-Anwendung. Dieses Dokument beschreibt die tatsächlich implementierten Schutzgrenzen. Es ist keine Behauptung absoluter Sicherheit; reale Home-Assistant-, Netzwerk- und iPhone-Integration müssen auf dem Zielsystem zusätzlich verifiziert werden.

## Netzwerk- und Vertrauensgrenzen

Die Hauptanwendung auf Port 8099 ist ausschließlich für Home Assistant Ingress vorgesehen. Der Port ist in `config.yaml` standardmäßig nicht auf den Host veröffentlicht. Zusätzlich prüft die Anwendung in Produktion die **reale TCP-Quelladresse**: nur der Home-Assistant-Ingress-Proxy `172.30.32.2` darf auf die UI/API zugreifen. Loopback ist ausschließlich für `/api/health` zugelassen. `X-Forwarded-For`, `X-Hass-Source` und `X-Ingress-Path` werden nicht als Vertrauenssignal verwendet. Uvicorn läuft mit `--no-proxy-headers`, sodass gefälschte Forwarding-Header die Peer-Adresse nicht überschreiben können.

Der optionale Health-Auto-Export-Gateway läuft getrennt auf Port 8100 und stellt nur `/health` und `POST /health-auto-export` bereit. OpenAPI-/Swagger-/ReDoc-Endpunkte sind deaktiviert. Port 8100 wird **gar nicht gestartet**, solange kein ausreichend starker Sync-Token konfiguriert ist. Auch Port 8100 ist standardmäßig nicht auf den Home-Assistant-Host veröffentlicht.

**Port 8100 niemals als unverschlüsseltes HTTP ins Internet weiterleiten.** Für Nutzung außerhalb des Heimnetzes ist ein verschlüsseltes VPN wie WireGuard/Tailscale oder ein korrekt konfigurierter HTTPS-Reverse-Proxy mit TLS, Verbindungs-/Request-Timeouts und sinnvoller Rate-Begrenzung erforderlich.

## Health Auto Export

- eigener, von OpenAI- und Home-Assistant-Zugangsdaten getrennter Token
- mindestens 48 Zeichen, höchstens 256 Zeichen, keine Leerzeichen, Mindestdiversität; empfohlen wird ein kryptografisch zufälliger Token
- timing-resistenter Vergleich über `hmac.compare_digest`
- Authentifizierung erfolgt **vor** dem Lesen des Request-Bodys
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

`openai_api_key` und `health_auto_export_token` sind Home-Assistant-Passwortoptionen und werden nicht durch die Laufapp-API an das Frontend ausgegeben. Dateierzeugung erfolgt mit restriktivem `umask 077`.

## OpenAI / KI

Der OpenAI-Key bleibt serverseitig. Der Coach erhält nur den für die konkrete Analyse zusammengestellten Trainingskontext. Screenshots werden nur nach expliziter Nutzeraktion an die OpenAI API gesendet und nicht dauerhaft als Bild gespeichert. KI-Vorschläge können den Trainingsplan nicht eigenständig verändern: Änderungen werden serverseitig validiert und müssen vom Nutzer ausdrücklich bestätigt werden.

## Browser / XSS

Die dynamischen Frontendpfade wurden auf Stored/Reflected XSS geprüft. Nutzer- und Modelldaten wie Coach-Antworten, Rennnamen, Notizen, Leistungslabels und Quellen werden vor HTML-Einfügung escaped. Externe Quellenlinks werden nur für `http:`/`https:` akzeptiert und mit `noopener noreferrer` geöffnet. Im geprüften Rendering-Pfad wurde keine offene Stored-XSS-Lücke gefunden.

## Supply Chain und CI

Direkte Runtime-Abhängigkeiten sind auf geprüfte Versionen gepinnt. `pip-audit` blockiert Releases bei bekannten Python-Abhängigkeitsschwachstellen. Der FastAPI-/Starlette-Stack wurde im Security-Review auf gepatchte Versionen aktualisiert. Zusätzlich läuft Bandit über den Python-Code; nur exakt dokumentierte Legacy-Findings mit geprüfter Nicht-Sicherheitsbedeutung dürfen den Review-Gate passieren, neue Medium/High-Findings blockieren die CI.

GitHub-Actions werden nicht über bewegliche Major-Tags geladen, sondern auf geprüfte Commit-SHAs gepinnt. Workflow-Rechte sind auf `contents: read` begrenzt.

## Bewusst verbleibende Risiken

Der Container läuft weiterhin im Home-Assistant-App-Modell mit den dort nötigen Dateirechten und besitzt für den bestehenden Repository-Transferpfad `/share:rw`. Eine Umstellung auf einen strikt nicht privilegierten Container beziehungsweise Entfernung des Share-Mounts würde das Home-Assistant-Persistenz-/Migrationsverhalten beeinflussen und wird ohne realen Supervisor-Test nicht vorgenommen. Diese Punkte sind lokale Host-/Container-Risiken, keine Begründung für eine öffentliche Portfreigabe.

Ein gültiger Health-Auto-Export-Token erlaubt weiterhin das **Schreiben** plausibler Health-Daten. Deshalb muss er wie ein Passwort behandelt und bei Verdacht sofort rotiert werden. Der Gateway ist bewusst write-only, damit derselbe Token nicht zum Auslesen persönlicher Laufdaten genutzt werden kann.

## Release-Grenze

Automatisiert geprüft werden Compile/Syntax, Regressionstests, Trainingssimulationen, Dependency-Audit, Bandit-Gate, Docker-Build, authentifizierter und unauthentifizierter Health-Auto-Export, idempotenter Reimport sowie ein absichtlich veröffentlichter Test-Port 8099 mit gefälschten Proxy-/Ingress-Headern. Die reale Home-Assistant-Ingress-Quelle, der reale Supervisor-Port-Mapping-Zustand, VPN/HTTPS-Konfiguration und Health Auto Export auf dem iPhone müssen nach Installation lokal verifiziert werden.
