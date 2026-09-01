# Laufapp v0.2.22

## Kalenderabstände und letzter erfolgreicher Datenabgleich

Bei zwei direkt aufeinanderfolgenden Lauftagen mit genau einer Qualitätseinheit plant Laufapp normalerweise zuerst die Qualitätseinheit und danach den Easy Run. Zwischen Schlüsselbelastungen werden kalenderbasiert möglichst mindestens 48 Stunden eingeplant. Neben Quality, Race-Prep und Rennen zählen spezifische sowie sehr lange Longruns ab 24 km oder geschätzten 120 Minuten als Schlüsselbelastung.

Die automatische Optimierung darf nur zukünftige, weiterhin geplante und unveränderte Engine-Slots für Easy, Quality und Race-Prep neu zuordnen. Longrun-/Renntage sowie manuell verschobene, absolvierte, ausgefallene oder verknüpfte Einheiten bleiben geschützt. Nicht sicher lösbare Konflikte werden im lokalen Safety Check angezeigt.

Direkt oberhalb von **Nächste Einheit** zeigt der Heute-Tab den Zeitpunkt und die Quelle der jüngsten erfolgreichen Datensynchronisierung. Berücksichtigt werden vollständig verarbeitete Health-Auto-Export-Requests und vollständig abgeschlossene Apple-Health-ZIP/XML-Hintergrundimporte. Fehlgeschlagene, abgebrochene oder laufende Importe zählen nicht. Die App speichert den Zeitpunkt in UTC und formatiert ihn im Browser als lokale deutsche Datums- und Uhrzeitangabe. Vor dem ersten Erfolg erscheint ein eindeutiger Leerzustand.

Der Ingress-robuste Inline-Header, die PWA-Icon-Härtung und alle Security-Grenzen aus v0.2.21 bleiben erhalten. Der Home-Assistant-Relay bleibt unverändert auf seiner eigenen Version 0.2.19. Keine Datenbankschemamigration.

## Validierung

- **177/177 Pytests** bestanden, einschließlich der bestehenden Inline-Icon-/PNG-Regressionssuite und neuer Kalender-, Sync-, Fehler- und UI-Reihenfolgetests.
- Python-Compilecheck sowie JavaScript- und Shell-Syntaxchecks bestanden.
- 16-Wochen-Marathonsimulation und neun randomisierte Läuferprofile bestanden.
- Direkter Uvicorn-Prozess-E2E mit 48-h-Kalenderfeld, authentifiziertem Health Auto Export, anschließendem Apple-Health-ZIP-Hintergrundimport, Quellenwechsel zum jüngeren Erfolg, ausgeliefertem v0.2.22-Frontend und SQLite-Integritätsprüfung bestanden.
- Bandit-Gate und Dependency-Konsistenz bestanden.

Docker-Build, Git-History-Secret-Scan, Dependency-Audit und die vollständigen Home-Assistant-/Ingress-E2E-Gates werden zusätzlich durch GitHub Actions ausgeführt. Die tatsächliche Darstellung auf iPhone und in Home Assistant OS/Ingress bleibt nach Installation lokal zu verifizieren.
