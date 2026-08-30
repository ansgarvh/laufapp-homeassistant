from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

# These are reviewed legacy source patterns. They remain statically visible even
# though v0.2.7 replaces the XML parser at runtime before imports execute. Exact
# file/test/line matching is intentional: moving or adding a finding requires a
# fresh human review rather than silently extending this allow-list.
ALLOWED = {
    ("laufapp/app/health_import.py", "B314", 387),
    ("laufapp/app/health_import.py", "B314", 475),
    # SHA-1 is used solely as a non-security deterministic tie-break value.
    ("laufapp/app/training_planner_v020.py", "B324", 147),
    # Dynamic SQL identifiers come only from the fixed three-column whitelist;
    # every user value remains a bound SQLite parameter.
    ("laufapp/app/main.py", "B608", 252),
}

# Verify the assumptions behind the allow-list have not silently changed.
hardening = (ROOT / "laufapp/app/health_import_hardening_v027.py").read_text(encoding="utf-8")
assert "health.ET = DefusedET" in hardening
assert "from defusedxml import ElementTree as DefusedET" in hardening
planner = (ROOT / "laufapp/app/training_planner_v020.py").read_text(encoding="utf-8")
assert 'hashlib.sha1(f"{ws.isoformat()}:{key}".encode())' in planner
main = (ROOT / "laufapp/app/main.py").read_text(encoding="utf-8")
assert "for k in ('rpe','shoe_id','notes')" in main
assert 'c.execute(f"UPDATE runs SET {\',\'.join(parts)} WHERE id=?",(*args,rid))' in main

unexpected = []
seen_allowed = set()
for issue in report.get("results", []):
    severity = issue.get("issue_severity")
    confidence = issue.get("issue_confidence")
    if severity not in {"MEDIUM", "HIGH"} or confidence not in {"MEDIUM", "HIGH"}:
        continue
    filename = str(Path(issue["filename"]).as_posix())
    if filename.startswith(str(ROOT.as_posix()) + "/"):
        filename = filename[len(str(ROOT.as_posix())) + 1 :]
    key = (filename, issue["test_id"], int(issue["line_number"]))
    if key in ALLOWED:
        seen_allowed.add(key)
    else:
        unexpected.append(issue)

if unexpected:
    print(json.dumps(unexpected, indent=2), file=sys.stderr)
    raise SystemExit("Unexpected medium/high-confidence Bandit findings")

missing = ALLOWED - seen_allowed
if missing:
    raise SystemExit(f"Reviewed Bandit finding disappeared or moved; re-review allow-list: {sorted(missing)!r}")

print(f"Bandit gate passed; {len(seen_allowed)} reviewed legacy findings explicitly accounted for.")
