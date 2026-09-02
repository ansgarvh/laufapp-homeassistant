# Laufapp v0.2.26 – Health-Auto-Export-Gesundheitsdaten

v0.2.26 repariert den Import allgemeiner Gesundheitsdaten aus dem aktuellen JSON-v2-Format von Health Auto Export. Die Änderung ist eine additive Kompatibilitätsschicht oberhalb des bestehenden gehärteten Importers. Lauf-Workouts, detaillierte Messreihen, GPS, Home-Assistant-Ingress und der Nabu-Casa-Relay bleiben unverändert.

## Behobene Ursachen

Das aktuelle HAE-Format bezeichnet Gewicht als `weight_body_mass` und VO₂max als `vo2max`. v0.2.25 kannte nur ältere Varianten, wodurch beide Metriken ohne Fehlermeldung übersprungen wurden.

Aktuelle Schlafdatensätze liefern die Phasen `core`, `rem`, `deep`, `awake` und `inBed`. Der bisherige Parser erwartete dagegen `totalSleep`, `asleep` oder `qty` und importierte deshalb keine aktuellen Schlafdatensätze. v0.2.26 berechnet die Schlafdauer fachlich als Core + REM + Deep. Wachzeit und reine Im-Bett-Zeit zählen nicht als Schlaf.

## Einheiten und vorhandene Daten

- Gewicht wird vor der Speicherung nach Kilogramm normalisiert. Unterstützt werden kg, g, lb/lbs und Stone.
- Bereits vorhandene HAE-Gewichtszeilen mit einer eindeutig als Pfund ausgewiesenen Einheit werden beim nächsten HAE-Import atomar nach Kilogramm korrigiert.
- HRV/SDNN wird in Millisekunden gespeichert; als Sekunden gelieferte Werte werden umgerechnet.
- Ruhepuls wird als bpm und Schlafdauer als Stunden gespeichert.
- Unbekannte Einheiten sowie unplausible Gewicht-, HRV-, Ruhepuls-, Schlaf- oder VO₂max-Werte führen zu einem validierten Importfehler und werden nicht stillschweigend falsch gespeichert.
- Bei einer überlappenden erneuten HAE-Übertragung wird ein bereits von HAE gespeicherter Wert desselben Zeitpunkts aktualisiert, wenn sich sein Inhalt geändert hat. Das ist insbesondere für zunächst unvollständige und später von Apple finalisierte Schlafnächte wichtig. Werte aus dem klassischen Apple-Health-XML-Import werden nicht überschrieben.

## Kompatibilität

- Keine Datenbankschemamigration.
- Bestehende Aliasnamen für Gewicht, VO₂max, HRV und Schlaf bleiben unterstützt.
- Bestehende Läufe, Laufmessreihen, GPS-Punkte, Bestzeiten, Schuhe, Rennen, Trainingsplan, Einstellungen und Coach-Daten bleiben erhalten.
- Die HAE-Authentifizierung, Body-/Zeit-/Rate-/Parallelitätsgrenzen, der klassische Apple-Health-ZIP/XML-Import und die Ingress-Sicherheitsgrenze bleiben unverändert.
- `custom_components/laufapp_hae_relay` bleibt auf seiner unabhängigen Version `0.2.19`, weil dessen Transportimplementierung nicht geändert wird.

## Verifikation

Die Release-Gates prüfen die aktuelle HAE-Metrikstruktur synthetisch und über den vollständigen HTTP-/Relay-Pfad. Zusätzlich laufen die vollständige Pytest-Regression, Python-/JavaScript-/Shell-Syntaxprüfungen, Trainingssimulationen, Dependency-/Security-Gates, Docker-Build und Docker-E2E.

Statisch/isoliert und in Linux/Docker getestet. Die echte Home-Assistant-OS-/Custom-Integration-/Nabu-Casa-Remote-UI-/Health-Auto-Export-iPhone-Integration muss nach Installation auf dem Zielsystem lokal verifiziert werden.
