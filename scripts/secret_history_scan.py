from __future__ import annotations

import re
import subprocess
import sys


PATTERNS = {
    "OpenAI/API key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    "GitHub token": re.compile(r"\b(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    "Private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "JWT-like token": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    "Nabu Casa webhook": re.compile(
        r"https://[A-Za-z0-9_-]{12,}\.ui\.nabu\.casa/api/webhook/[A-Za-z0-9_-]{20,}"
    ),
}

# Literal examples used by tests are intentionally not generic secret patterns.
# Placeholders containing '<...>' or REPLACE_WITH are not matched by PATTERNS.


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def main() -> int:
    commits = [line.strip() for line in _git("rev-list", "--all").splitlines() if line.strip()]
    findings: list[str] = []
    seen: set[tuple[str, str, str]] = set()

    for commit in commits:
        files = [line for line in _git("ls-tree", "-r", "--name-only", commit).splitlines() if line]
        for path in files:
            if path.endswith((".png", ".jpg", ".jpeg", ".ico", ".zip")):
                continue
            try:
                content = _git("show", f"{commit}:{path}")
            except subprocess.CalledProcessError:
                continue
            for name, pattern in PATTERNS.items():
                match = pattern.search(content)
                if not match:
                    continue
                fingerprint = (name, path, match.group(0)[:24])
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                findings.append(f"{name}: {commit[:12]} {path}")

    if findings:
        print("Potential secrets found in Git history:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1

    print(f"Secret-history scan passed across {len(commits)} commits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
