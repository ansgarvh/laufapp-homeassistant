# Laufapp v0.2.13

## Ziel

v0.2.13 bereinigt nach dem real bestätigten Health-Auto-Export-Fix aus v0.2.12 alte Relikte, reduziert Home-Assistant-/Webhook-Angriffsfläche und ergänzt unter **Fortschritt** eine längerfristige Trainingsentwicklung. Es gibt keine Datenbankschemamigration und keine Änderung an der Trainingsplanlogik.

## Bereinigung

- `.DS_Store`-Metadaten aus dem Repository entfernt und per `.gitignore` dauerhaft ausgeschlossen.
- Die alten Home-Assistant-Beispiele `automation_laufapp_nabu_casa.yaml.example` und `rest_command_laufapp_nabu_casa.yaml.example` entfernt. Der produktive Weg ist ausschließlich die Custom Integration `laufapp_hae_relay`.
- Der einmalige GitHub-Umzug ist abgeschlossen. Der produktive API-Endpunkt `/api/system/prepare-repository-transfer` wird nicht mehr registriert.
- Der nur hierfür benötigte Home-Assistant-Mount `share:rw` wurde aus `config.yaml` entfernt. Die Laufapp hat damit keinen Zugriff mehr auf `/share`.
- Die historische interne Transfer-/Adoptionslogik bleibt im Quellcode als Recovery-/Altkompatibilität bestehen; sie ist ohne `/share`-Mount und ohne öffentlichen Vorbereitungsendpunkt im normalen Betrieb inaktiv.

## Security-Härtung

- HAE-Webhooks bleiben POST-only, JSON-only, auf 16 MiB begrenzt, mit starker nicht erratbarer Webhook-ID und separatem internem Laufapp-Token.
- Neu: 120-Sekunden-Limit schon beim Lesen des öffentlichen Webhook-Bodys gegen Slow-Request-DoS.
- Neu: maximal 12 HAE-Webhookrequests pro Minute und maximal drei parallele Forwardings. Überlast wird mit HTTP 429 abgewiesen.
- Feste interne Relay-Zieladresse bleibt erhalten; dadurch kein nutzergesteuertes SSRF-Ziel.
- Browserseitige Cross-Site-Schreibrequests mit `Sec-Fetch-Site: cross-site` werden mit HTTP 403 blockiert.
- Hauptanwendung setzt `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, restriktive `Permissions-Policy` und Content-Security-Policy für lokale Ressourcen.
- Coach-Historie erhält ein serverseitiges Limit von 1 bis 200 Einträgen.
- Security-CI führt zusätzlich `pip check` und einen Git-History-Secret-Scan über alle erreichbaren Branches aus. Gesucht werden typische OpenAI-/GitHub-Tokens, JWTs, Private Keys und reale Nabu-Casa-Webhook-URLs.
- Bestehende Schutzmaßnahmen bleiben erhalten: Ingress-Vertrauensgrenze, keine Host-Port-Veröffentlichung für 8099/8100, Authentifizierung vor HAE-Body-Lesen, HAE-Mengenlimits, ZIP-/GPX-Grenzen, `defusedxml`, pip-audit, Bandit und write-only Gateway-Antworten.

## Trainingsentwicklung unter Fortschritt

Neuer Bereich am unteren Ende von **Fortschritt** mit Zeitachse für 3, 6, 12 oder 24 Monate. Wählbare Kennzahlen:

- Laufkilometer pro Woche
- distanzgewichtete durchschnittliche Pace
- Kadenz
- Laufzeit pro Woche
- Läufe pro Woche
- durchschnittliche Laufdistanz
- längster Lauf
- durchschnittliche Herzfrequenz
- durchschnittliches RPE
- Höhenmeter, soweit gespeichert
- Ruhepuls
- HRV / SDNN
- Schlafdauer
- Gewicht
- VO₂max

Die API liefert ausschließlich begrenzte Wochenaggregate. Roh-GPS-Punkte oder komplette Health-Zeitreihen werden für die Darstellung nicht an den Browser übertragen. Fehlende Daten bleiben Lücken; die App erfindet keine Werte. Pace, Herzfrequenz und Kadenz werden sinnvoll gewichtet statt einfache Laufmittel zu bilden.

## Home-Assistant-Aufräumhinweise

Nach erfolgreichem Update auf v0.2.13 können auf dem Zielsystem vorhandene Alt-Konfigurationen entfernt werden:

- alte Automation **„Laufapp - Health Auto Export via Nabu Casa (legacy small payload)“**, falls noch vorhanden;
- alter `rest_command.laufapp_health_auto_export_relay`, falls noch in `configuration.yaml`/Includes vorhanden;
- eventuell verbliebener Ordner `/share/laufapp-transfer/`, sofern die aktuelle GitHub-Laufapp bereits korrekt mit ihren persistenten Daten läuft.

Nicht entfernen: den aktuellen `laufapp_hae_relay:`-Block sowie die dafür verwendeten Secrets `laufapp_hae_webhook_id` und `laufapp_health_auto_export_token`.

## Testanforderung

Release erst bei vollständig grünen Gates: Compilecheck, JavaScript-Syntax, vollständige Pytest-Regression, HAE-Realformat-Regression, Relay-Größen-/Rate-/Slow-Body-Tests, Marathon- und Randomprofil-Simulationen, `pip check`, `pip-audit`, Git-History-Secret-Scan, Bandit, Docker-Build, direkter HAE-E2E, interner Relay-E2E, Ingress-Spoofing-Negativtests, positive HA-Ingress-Simulation und Gateway-fail-closed.

Statisch/isoliert und in Linux/Docker getestet; die reale Home-Assistant-OS-/Nabu-Casa-/Health-Auto-Export-iPhone-Integration muss nach Installation lokal verifiziert werden.
