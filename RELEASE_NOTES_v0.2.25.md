# Laufapp v0.2.25 – Laufdetails

v0.2.25 erweitert die bestehende v0.2.24-Anwendung um eine eigenständige Detailansicht für bereits erkannte Läufe. Die Trainingsengine, Health-Auto-Export-Pipeline, Home-Assistant-Ingress-Sicherheitsgrenzen und der separat versionierte Home-Assistant-Relay bleiben unverändert.

## Neue Laufdetailansicht

Ein gespeicherter Lauf kann unter **Fortschritt** direkt geöffnet werden. Eine absolvierte Einheit in der **Wochenübersicht** öffnet dieselbe Ansicht, wenn sie mit einem realen Lauf verknüpft ist beziehungsweise eindeutig einem Lauf desselben Tages zugeordnet werden kann.

Die Detailansicht zeigt – abhängig von den tatsächlich gespeicherten Quelldaten – Strecke, Trainingszeit, verstrichene Zeit, durchschnittliche Pace, Höhenmeter, Herzfrequenz, Running Power, Kadenz, Aktivitätskalorien, subjektive Anstrengung/RPE, Schrittlänge, vertikale Oszillation und Bodenkontaktzeit. Die vorhandene Bearbeitung eigener Angaben sowie das KI-Feedback für den einzelnen Lauf bleiben über **Eigene Angaben & KI-Feedback** erreichbar.

## Verlaufskurven

Aus `run_samples` und `gps_points` werden lokale Verlaufskurven für Höhe, Herzfrequenz, Pace, Leistung, Kadenz, vertikale Oszillation, Bodenkontaktzeit und Schrittlänge erzeugt. Nicht vorhandene Messreihen bleiben als klarer Leerzustand sichtbar und werden nicht geschätzt.

Die API begrenzt die an den Browser übertragenen Visualisierungspunkte auf höchstens 240 Punkte je Messreihe und 700 GPS-Punkte. Die vollständigen persistenten Rohdaten in SQLite werden dadurch nicht verändert oder gelöscht.

## GPS-Strecke und Datenschutz

Vorhandene GPS-Punkte werden als lokale SVG-Streckengrafik mit Start-/Endmarker dargestellt. v0.2.25 bindet bewusst keinen externen Karten- oder Tile-Dienst ein. Damit werden keine GPS-Rohkoordinaten für die Kartenanzeige an einen Dritten übertragen und die bestehende Content-Security-Policy muss nicht erweitert werden.

Die Darstellung ist daher eine Streckengrafik auf einer dezenten Laufapp-Fläche und kein beschrifteter Straßenkarten-Layer. Ein späterer echter Basemap-Layer sollte nur mit einer datenschutzverträglichen, lokal gehosteten Lösung ergänzt werden.

## Gesamtkalorien

Die vorhandenen Importpfade speichern pro Lauf den verfügbaren Workout-/Aktivitätsenergie-Wert, aber keinen separat persistierten Apple-Fitness-Gesamtenergie-Wert aus Aktivitäts- plus Ruheenergie. v0.2.25 zeigt die Kachel **Gesamtkalorien** deshalb bewusst als nicht verfügbar und erfindet keinen Zuschlagswert.

## Kompatibilität

- Keine Datenbankschemamigration.
- Bestehende Läufe, GPS-Punkte, Messreihen, Schuhe, Bestzeiten, Rennen, Trainingsplan, Einstellungen und Coach-Daten bleiben erhalten.
- Health Auto Export, klassischer Apple-Health-ZIP/XML-Import, Nabu-Casa-Relay, Ingress-Guard und KI-Datensparsamkeitsregeln bleiben unverändert.
- `custom_components/laufapp_hae_relay` bleibt bei seiner unabhängigen Version `0.2.19`, weil dessen Implementierung nicht geändert wird.

## Verifikation

Die Release-Gates umfassen Python-Compilecheck, JavaScript-Syntax, vollständige Pytest-Regression, neue Laufdetail-/GPS-/Downsampling-Tests, 16-Wochen-Marathonsimulation, neun randomisierte Läuferprofile, Dependency-/Security-Gates, Docker-Build sowie Docker-E2E für Hauptapp, Health Auto Export, internen Home-Assistant-Relay und Ingress-Sicherheitsgrenzen.

Statisch/isoliert sowie in Linux/Docker verifiziert. Die echte Home-Assistant-OS-/iPhone-/Nabu-Casa-/Ingress-Darstellung muss nach Installation auf dem Zielsystem lokal verifiziert werden.
