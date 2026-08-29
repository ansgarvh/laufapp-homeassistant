from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from randomized_runner_simulator import SEEDS, simulate_scenario  # noqa: E402


@pytest.mark.parametrize("index,seed", list(enumerate(SEEDS)), ids=[f"runner-{i+1}" for i in range(len(SEEDS))])
def test_randomized_runner_profile(index: int, seed: int):
    """Nine reproducible randomized ability profiles must satisfy planner invariants end-to-end."""
    result = simulate_scenario(index, seed)
    assert result["weeks"] >= 9
    assert result["peak_week_km"] > 0
    assert result["quality_variants"] >= 3
