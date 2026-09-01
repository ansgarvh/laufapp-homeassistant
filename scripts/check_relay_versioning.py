#!/usr/bin/env python3
"""Enforce independent versioning for the Home Assistant HAE relay.

The Laufapp application and the Home Assistant custom relay have separate
release lifecycles. Normal Laufapp releases must not bump the relay manifest.
A relay implementation change must, however, carry an explicit relay version
increase so operators know when the Home Assistant custom component really
needs to be updated and Home Assistant restarted.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Iterable

RELAY_SOURCE = "custom_components/laufapp_hae_relay/__init__.py"
RELAY_MANIFEST = "custom_components/laufapp_hae_relay/manifest.json"
ZERO_SHA = "0" * 40
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def _version_tuple(version: str) -> tuple[int, int, int]:
    match = SEMVER_RE.fullmatch(version)
    if match is None:
        raise ValueError(f"Relay version must be numeric SemVer x.y.z, got {version!r}")
    return tuple(int(part) for part in match.groups())


def validate_transition(
    changed_paths: Iterable[str], base_version: str, head_version: str
) -> list[str]:
    """Return policy violations for one relay transition."""
    changed = set(changed_paths)
    source_changed = RELAY_SOURCE in changed
    version_changed = base_version != head_version
    errors: list[str] = []

    try:
        base_tuple = _version_tuple(base_version)
        head_tuple = _version_tuple(head_version)
    except ValueError as exc:
        return [str(exc)]

    if source_changed and not version_changed:
        errors.append(
            "HAE relay implementation changed but manifest version did not. "
            "Bump only the relay version intentionally."
        )
    elif source_changed and version_changed and head_tuple <= base_tuple:
        errors.append(
            f"HAE relay implementation changed, but version did not increase: "
            f"{base_version} -> {head_version}."
        )

    if version_changed and not source_changed:
        errors.append(
            "HAE relay manifest version changed without a relay implementation change. "
            "Normal Laufapp releases must leave the relay version untouched."
        )

    return errors


def _manifest_version(ref: str) -> str:
    payload = json.loads(_git("show", f"{ref}:{RELAY_MANIFEST}"))
    version = payload.get("version")
    if not isinstance(version, str) or not version:
        raise RuntimeError(f"Missing relay version in {RELAY_MANIFEST} at {ref}")
    return version


def _resolve_base(base: str, head: str) -> str:
    if not base or base == ZERO_SHA or base == head:
        return _git("rev-parse", f"{head}^").strip()
    return base


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {argv[0]} <base-sha> <head-sha>", file=sys.stderr)
        return 2

    base = _resolve_base(argv[1], argv[2])
    head = argv[2]
    changed = _git(
        "diff",
        "--name-only",
        base,
        head,
        "--",
        RELAY_SOURCE,
        RELAY_MANIFEST,
    ).splitlines()
    base_version = _manifest_version(base)
    head_version = _manifest_version(head)
    errors = validate_transition(changed, base_version, head_version)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(
        "HAE relay versioning OK: "
        f"relay {base_version} -> {head_version}; "
        f"implementation_changed={RELAY_SOURCE in set(changed)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
