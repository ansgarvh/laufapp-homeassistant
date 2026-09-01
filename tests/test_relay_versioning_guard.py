from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts/check_relay_versioning.py"

spec = importlib.util.spec_from_file_location("laufapp_relay_version_guard", GUARD)
assert spec is not None and spec.loader is not None
relay_version_guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay_version_guard)

RELAY_SOURCE = relay_version_guard.RELAY_SOURCE
validate_transition = relay_version_guard.validate_transition


def test_normal_laufapp_release_does_not_require_relay_bump():
    assert validate_transition(set(), "0.2.19", "0.2.19") == []


def test_relay_implementation_change_requires_version_bump():
    errors = validate_transition({RELAY_SOURCE}, "0.2.19", "0.2.19")
    assert errors and "implementation changed" in errors[0]


def test_relay_version_must_not_change_without_implementation_change():
    errors = validate_transition(set(), "0.2.19", "0.2.20")
    assert errors and "without a relay implementation change" in errors[0]


def test_relay_change_with_increased_version_is_allowed():
    assert validate_transition({RELAY_SOURCE}, "0.2.19", "0.2.20") == []


def test_relay_version_cannot_move_backwards_on_code_change():
    errors = validate_transition({RELAY_SOURCE}, "0.2.19", "0.2.18")
    assert errors and "did not increase" in errors[0]


def test_relay_version_is_strict_numeric_semver():
    errors = validate_transition(set(), "0.2.19", "app-0.2.19")
    assert errors and "numeric SemVer" in errors[0]
