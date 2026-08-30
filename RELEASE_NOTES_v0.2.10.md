# Laufapp v0.2.10 – Nabu Casa Health Sync Relay

## Ziel

v0.2.10 ersetzt für die kontinuierliche iPhone-Synchronisation die Notwendigkeit eines direkt erreichbaren Laufapp-Ports durch einen Nabu-Casa-/Home-Assistant-Relay-Pfad. Die eigentliche Laufapp bleibt Home-Assistant-Ingress-only; der Health-Auto-Export-Gateway bleibt standardmäßig unveröffentlicht.

## Datenpfad

`Health Auto Export → HTTPS Nabu Casa Cloudhook → Home Assistant Webhook → interner REST Command → c87ed7df-laufapp:8100/home-assistant-relay → gehärteter HAE-Importer`

## Änderungen

- Neuer dedizierter Gateway-Endpunkt `POST /home-assistant-relay`.
- Der Relay-Endpunkt akzeptiert ausschließlich `X-Laufapp-Token`; ein Bearer-Token allein wird dort mit HTTP 401 abgewiesen.
- Der bestehende direkte `POST /health-auto-export`-Endpunkt bleibt für private/anderweitig verschlüsselte Transporte kompatibel erhalten.
- Port 8100 bleibt in `config.yaml` auf `null` und muss für den Nabu-Casa-Relay weder am Home-Assistant-Host noch am Router veröffentlicht werden.
- Home-Assistant-Beispiele für `rest_command` und Webhook-Automation ergänzt. Der Laufapp-Token wird über `!secret` referenziert und nicht in Automation/Repository eingebettet.
- Beispielautomation ist `queued` (`max: 50`) für HAE-Batch-Requests.
- Für Cloudhook-Synchronisation wird `Previous 7 Days / Letzte 7 Tage` statt `Since Last Sync` empfohlen. Hintergrund: Der generische Home-Assistant-Webhook bestätigt den Eingang, bevor die nachgelagerte Automation/REST-Aktion end-to-end abgeschlossen ist. Das überlappende Fenster nutzt die bestehende Idempotenz, um temporäre Relay-Ausfälle später nachzuholen.
- Erfolgreiche interne Zustellungen erzeugen einen datensparsamen Marker `LAUFAPP_HAE_RELAY_OK` mit ausschließlich Importzählern, ohne Token, Webhook-ID oder persönliche Messwerte.
- Produktions-Entry-Point auf `main_v0210:app` angehoben; bestehende v0.2.9-Implementierung wird unverändert übernommen.
- Keine Datenbankschemamigration und keine Änderung an Trainings-, Prognose-, Bestzeiten-, Apple-Health-Historien- oder Ingress-Logik.

## Zusätzliche Tests

- Relay ohne Token → 401.
- Relay nur mit Bearer-Token → 401.
- Relay mit starkem `X-Laufapp-Token` → erfolgreicher detaillierter Workout-/GPS-/Health-Import.
- Wiederholte Relay-Zustellung → idempotent, keine doppelten Samples/GPS-/Health-Werte.
- Docker-E2E über separates User-Defined-Network zum Gateway-Container, also unabhängig vom veröffentlichten Host-Port.
- Bestehender direkter HAE-E2E, Ingress-Spoofing-Negativtest, positive Home-Assistant-Ingress-Netzsimulation, Gateway-fail-closed-Test, vollständige Pytest-Regression, Trainingssimulationen, Compile-/JS-Syntax-, Dependency- und Security-Gates bleiben aktiv.

## Einrichtung nach Installation

Siehe `NABU_CASA_HEALTH_SYNC.md`. Erst nach einem erfolgreichen realen Cloudhook-Test soll die temporär manuell gesetzte Host-Port-Zuordnung für `8100/tcp` wieder entfernt werden.

## Testgrenze

Statisch/isoliert und in Linux/Docker getestet. Die reale Nabu-Casa-Cloudhook-Zustellung, der Home-Assistant-REST-Command über den realen Supervisor-internen DNS-Namen sowie Health Auto Export auf dem iPhone müssen lokal auf Home Assistant OS verifiziert werden.
