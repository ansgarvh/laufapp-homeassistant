# Laufapp v0.2.7 – Security-Härtung

v0.2.7 ist ein reines Sicherheits-/Robustheitsrelease auf Basis von v0.2.6. Trainingsplanung, Bestzeitenlogik und persistentes Datenbankschema werden nicht fachlich verändert.

## Behobene Sicherheitsprobleme

### Hohe Relevanz: spoofbare Home-Assistant-Ingress-Vertrauensgrenze

v0.2.6 startete Uvicorn mit `--forwarded-allow-ips='*'`. Zusammen mit der älteren Ingress-Prüfung hätte eine versehentliche Veröffentlichung von Port 8099 ermöglicht, Forwarding-/Ingress-Header zu fälschen. v0.2.7 vertraut keine Proxy-Header mehr und autorisiert in Produktion ausschließlich die reale TCP-Quelle `172.30.32.2`; Loopback ist nur für `/api/health` zulässig. Ein Docker-Negativtest veröffentlicht Port 8099 absichtlich und muss gefälschte `X-Forwarded-For`-/Home-Assistant-Header mit HTTP 403 abweisen.

### Hohe/Mittlere Relevanz: bekannte Starlette-Abhängigkeitsschwachstellen

Der Dependency-Audit meldete mehrere bekannte 2026er Findings gegen die zuvor aufgelöste Starlette-Version 0.50.0. Der Runtime-Stack wurde auf FastAPI 0.141.1 / Starlette 1.6.0 angehoben und direkte Produktionsabhängigkeiten wurden gepinnt. `pip-audit` ist nun verpflichtender CI-Gate.

### XML-/ZIP-/GPX-DoS und XML-Entities

Der klassische Apple-Health-Import streamte ZIP-Inhalte bereits ohne `extractall`, hatte aber keine expliziten Kompressionsverhältnis-/Dateianzahl-/GPX-Punktlimits und verwendete `xml.etree.ElementTree` für nicht vertrauenswürdige XML-Daten. v0.2.7 ergänzt ZIP-Bomb-Limits, Größen-/Routenlimits, Koordinatenvalidierung und `defusedxml` gegen Entity Expansion/externe XML-Referenzen.

### Health-Auto-Export-Gateway

- Port 8100 startet nur mit einem ausreichend starken Token (fail closed).
- Token mindestens 48 zufällige Zeichen, keine Leerzeichen, Mindestdiversität; timing-resistenter Vergleich.
- Authentifizierung vor dem Body-Lesen.
- JSON-only, 16-MiB-Streaminglimit und 120-Sekunden-Body-Timeout.
- begrenzte Gateway-Parallelität und kurze Keep-Alive-Zeit.
- OpenAPI/Swagger/ReDoc deaktiviert; Server-Header deaktiviert; `no-store`, `nosniff`, `no-referrer`.
- externe Sync-Antwort ist write-only und enthält keine Prognosen oder persönlichen Read-Daten.
- widersprüchliche Wiederverwendung einer Workout-ID wird abgelehnt.
- Cross-Source-Deduplizierung verhindert Doppelwerte beim Übergang vom alten Apple-Health-XML-Import zu Health Auto Export.

## Supply Chain und statische Analyse

GitHub Actions sind auf konkrete Commit-SHAs gepinnt und besitzen nur `contents: read`. Zusätzlich zu `pip-audit` läuft Bandit. Zwei Legacy-Findings werden bewusst und exakt geprüft: SHA-1 dient ausschließlich als deterministischer, nicht sicherheitsrelevanter Trainingsplan-Tiebreaker; die dynamische SQL-Zeile verwendet ausschließlich drei fest verdrahtete Spaltennamen und gebundene Werte. Die alten `ElementTree`-Zeilen bleiben statisch sichtbar, werden zur Laufzeit aber vor jedem Health-Import durch `defusedxml` ersetzt; der Gate verifiziert genau diese Annahme. Neue Medium/High-Bandit-Findings blockieren den Build.

## Frontend

Die dynamischen HTML-Renderpfade für Coach-Antworten, Notizen, Rennnamen, Bestzeit-Labels und Quellen wurden auf Stored/Reflected XSS geprüft. Nutzerdaten werden escaped; externe Quellenlinks sind auf HTTP/HTTPS beschränkt und werden mit `noopener noreferrer` geöffnet. Im geprüften Pfad wurde keine offene Stored-XSS-Lücke gefunden.

## Daten und Kompatibilität

Keine Datenbankschemamigration. Bestehende Läufe, Apple-Health-Daten, Bestzeiten, Schuhe, Rennen, Trainingsplan, Einstellungen und Coach-Daten bleiben erhalten. Der manuelle ZIP/XML-Import und Health Auto Export bleiben beide verfügbar.

## Verbleibende Betriebsanforderung

Port 8099 niemals direkt veröffentlichen. Port 8100 ebenfalls nicht unverschlüsselt ins Internet weiterleiten; für externen Sync ausschließlich VPN oder einen korrekt konfigurierten HTTPS-Reverse-Proxy verwenden. Der Container und `/share:rw` bleiben wegen Home-Assistant-Persistenz-/Transferkompatibilität unverändert; eine weitere Privilegienreduktion erfordert einen realen Supervisor-Test.

Statisch/isoliert und in Linux/Docker getestet. Die reale Home-Assistant-/Supervisor-/VPN-/Health-Auto-Export-iPhone-Integration muss nach Installation lokal verifiziert werden.
