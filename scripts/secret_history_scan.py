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
GREP_PATTERN = (
    r"sk-(proj-)?[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|"
    r"https://[A-Za-z0-9_-]{12,}\.ui\.nabu\.casa/api/webhook/[A-Za-z0-9_-]{20,}"
)


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main() -> int:
    commits = [
        line.strip()
        for line in _git("rev-list", "--all").stdout.splitlines()
        if line.strip()
    ]
    findings: list[str] = []
    seen: set[tuple[str, str, str]] = set()

    for commit in commits:
        result = _git("grep", "-I", "-n", "-E", GREP_PATTERN, commit, "--", ".", check=False)
        if result.returncode not in {0, 1}:
            print(result.stderr, file=sys.stderr)
            return 2
        for line in result.stdout.splitlines():
            # git grep output is <commit>:<path>:<line>:<content>.
            parts = line.split(":", 3)
            if len(parts) != 4:
                continue
            _commit_ref, path, _line_no, content = parts
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
