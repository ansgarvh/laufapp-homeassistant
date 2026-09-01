# Laufapp v0.2.19

## Manuelle Absolvierung sicher zurücknehmen

Eine Planaktivität, die ohne verknüpften Lauf manuell als absolviert markiert wurde, kann im Einheiten-Menü wieder auf **geplant** gesetzt werden. Die Rücknahme löscht weder die Planaktivität noch Laufdaten.

Workouts mit einem echten `linked_run_id` werden bewusst anders behandelt: Der verknüpfte Lauf ist autoritativ. Das Backend lehnt ein Zurücksetzen auf `planned` oder `skipped` mit HTTP 409 ab, bis die Aktivitätsverknüpfung separat gelöst wurde. So können Status und vorhandener Lauf nicht widersprüchlich werden.

Das bestehende Response-Format des Status-Endpunkts bleibt für vorhandene Aufrufer rückwärtskompatibel bei `{"ok": true}`; die neue Absicherung verändert damit keine erfolgreiche Client-Antwort.

Keine Datenbankschemamigration. Die v0.2.18-Mehrfachrennenlogik, Leistungsprofil-, Apple-Health-/HAE-, Nabu-Casa-/Ingress- und Security-Schichten bleiben erhalten.

Statisch/isoliert und in Linux/Docker zu testen; die reale Home-Assistant-OS-/Ingress-Darstellung muss lokal verifiziert werden.
