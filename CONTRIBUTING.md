# Laufapp Entwicklungs- und CI-Ablauf

Ziel ist eine vollständige Release-Absicherung ohne unnötige GitHub-Actions-Läufe auf unfertigen Zwischenständen.

## Branch und Pull Request

1. Änderungen zunächst vollständig auf einem Entwicklungsbranch umsetzen.
2. Den Pull Request erst öffnen, wenn die geplante Implementierung und die zugehörigen Tests logisch vollständig sind.
3. Erst mit dem Pull Request startet die vollständige CI für den Branch.
4. Falls nach dem Öffnen des Pull Requests weitere Commits nötig sind, wird ein noch laufender CI-Lauf dieses Pull Requests automatisch abgebrochen und durch den Lauf für den neuesten Commit ersetzt.
5. Vor dem Merge muss der aktuelle Pull-Request-Stand vollständig grün sein.
6. Ein Push auf `main` führt weiterhin eine vollständige abschließende CI aus.

## Vollständige CI

Die Testtiefe wird nicht reduziert. Die Pipeline umfasst weiterhin:

- Python-Compilecheck
- JavaScript-Syntaxchecks
- vollständige Pytest-Regression
- 16-Wochen-Marathonsimulation
- neun reproduzierbar randomisierte Läuferprofile
- Home-Assistant-Docker-Build
- Docker-Runtime-Smoke-Test

Damit werden veraltete Zwischenläufe reduziert, ohne die eigentliche Release- und Regressionssicherheit zu schwächen.
