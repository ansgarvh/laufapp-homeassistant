# Laufapp v0.2.25 – Laufdetails

v0.2.25 erweitert die bestehende v0.2.24-Anwendung um eine eigenständige Detailansicht für bereits erkannte Läufe. Die Trainingsengine, Home-Assistant-Ingress-Sicherheitsgrenzen, der HAE-/Nabu-Casa-Transport und der separat versionierte Home-Assistant-Relay bleiben unverändert.

## Neue Laufdetailansicht

Ein gespeicherter Lauf kann unter **Fortschritt** direkt geöffnet werden. Eine absolvierte Einheit in der **Wochenübersicht** öffnet dieselbe Ansicht, wenn sie mit einem realen Lauf verknüpft ist beziehungsweise eindeutig einem Lauf desselben Tages zugeordnet werden kann.

Die Detailansicht zeigt – abhängig von den tatsächlich gespeicherten Quelldaten – Strecke, Trainingszeit, verstrichene Zeit, durchschnittliche Pace, Höhenmeter, Herzfrequenz, Running Power, Kadenz, Aktivitätskalorien, Gesamtkalorien, subjektive Anstrengung/RPE, Schrittlänge, vertikale Oszillation und Bodenkontaktzeit. Die vorhandene Bearbeitung eigener Angaben sowie das KI-Feedback für den einzelnen Lauf bleiben über **Eigene Angaben & KI-Feedback** erreichbar.

## Verlaufskurven

Aus `run_samples` und `gps_points` werden lokale Verlaufskurven für Höhe, Herzfrequenz, Pace, Leistung, Kadenz, vertikale Oszillation, Bodenkontaktzeit und Schrittlänge erzeugt. Nicht vorhandene Messreihen bleiben als klarer Leerzustand sichtbar und werden nicht geschätzt.

Die API begrenzt die an den Browser übertragenen Visualisierungspunkte auf höchstens 240 Punkte je Messreihe und 700 GPS-Punkte. Die vollständigen persistenten Rohdaten in SQLite werden dadurch nicht verändert oder gelöscht.

## GPS-Strecke und Datenschutz

Vorhandene GPS-Punkte werden als lokale SVG-Streckengrafik mit Start-/Endmarker dargestellt. v0.2.25 bindet bewusst keinen externen Karten- oder Tile-Dienst ein. Damit werden keine GPS-Rohkoordinaten für die Kartenanzeige an einen Dritten übertragen und die bestehende Content-Security-Policy muss nicht erweitert werden.

Die Darstellung ist daher eine Streckengrafik auf einer dezenten Laufapp-Fläche und kein beschrifteter Straßenkarten-Layer. Ein späterer echter Basemap-Layer sollte nur mit einer datenschutzverträglichen, lokal gehosteten Lösung ergänzt werden.

## Gesamtkalorien

v0.2.25 nutzt ein vorhandenes HAE-Feld `totalEnergy`, wenn Health Auto Export es für einen Lauf mitsendet. Dieser Wert wird **separat** als `total_calories` in der bestehenden Tabelle `run_samples` persistiert und niemals anstelle der Aktivitätskalorien verwendet. Damit bleiben Aktivitätsenergie und Gesamtenergie fachlich getrennt, ohne eine Datenbankschemamigration einzuführen.

Historische Läufe beziehungsweise Quellen ohne separaten Gesamtenergie-Wert zeigen bei **Gesamtkalorien** weiterhin `–`. Laufapp leitet dort keinen Zuschlagswert aus den Aktivitätskalorien ab.

## Kompatibilität

- Keine Datenbankschemamigration.
- Bestehende Läufe, GPS-Punkte, Messreihen, Schuhe, Bestzeiten, Rennen, Trainingsplan, Einstellungen und Coach-Daten bleiben erhalten.
- Health-Auto-Export-Authentifizierung, Größen-/Rate-/Parallelitätslimits, Nabu-Casa-Relay, klassischer Apple-Health-ZIP/XML-Import, Ingress-Guard und KI-Datensparsamkeitsregeln bleiben unverändert.
- Der HAE-Parser erhält ausschließlich die additive Speicherung von `totalEnergy`; bestehende aktive Energie bleibt weiterhin autoritativ für `runs.calories`.
- `custom_components/laufapp_hae_relay` bleibt bei seiner unabhängigen Version `0.2.19`, weil dessen Implementierung nicht geändert wird.

## Verifikation

Die Release-Gates umfassen Python-Compilecheck, JavaScript-Syntax, vollständige Pytest-Regression, neue Laufdetail-/GPS-/Downsampling-/Gesamtenergie-Tests, 16-Wochen-Marathonsimulation, neun randomisierte Läuferprofile, Dependency-/Security-Gates, Docker-Build sowie Docker-E2E für Hauptapp, Health Auto Export, internen Home-Assistant-Relay und Ingress-Sicherheitsgrenzen.

Die echte Home-Assistant-OS-/iPhone-/Nabu-Casa-/Ingress-Darstellung kann in der GitHub-/Linux-Umgebung nicht real getestet werden und muss nach Installation auf dem Zielsystem lokal verifiziert werden.
