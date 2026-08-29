from __future__ import annotations

from typing import Any

from db import get_setting, set_setting
from training_models_v020 import TrainingPhase

VERY_PROGRESSIVE = "very_progressive"
EXTRA_WEEKLY_TARGET = 0.025
_VALID_BASE_PROFILES = {"gradual", "steady", "progressive"}


def semantic_profile(c) -> str:
    """Return the user-facing four-level planning profile.

    The mature planner only knows gradual/steady/progressive.  The fourth level is
    deliberately stored as progressive plus a separate additive overlay so older
    code paths stay backward compatible instead of seeing an unknown enum value.
    """
    raw = str(get_setting(c, "training_volume_profile", "steady") or "steady")
    if raw not in _VALID_BASE_PROFILES:
        raw = "steady"
    try:
        boost = float(get_setting(c, "training_volume_boost_pct", 0.0) or 0.0)
    except (TypeError, ValueError):
        boost = 0.0
    if raw == "progressive" and boost >= 0.02:
        return VERY_PROGRESSIVE
    return raw


def extra_weekly_target_fraction(c) -> float:
    return EXTRA_WEEKLY_TARGET if semantic_profile(c) == VERY_PROGRESSIVE else 0.0


def set_semantic_profile(c, profile: str) -> None:
    if profile == VERY_PROGRESSIVE:
        set_setting(c, "training_volume_profile", "progressive")
        set_setting(c, "training_volume_boost_pct", EXTRA_WEEKLY_TARGET)
        return
    if profile not in _VALID_BASE_PROFILES:
        raise ValueError("Unbekannte Planungsaggressivität.")
    set_setting(c, "training_volume_profile", profile)
    set_setting(c, "training_volume_boost_pct", 0.0)


def install(training_module: Any) -> None:
    """Install a narrow overlay on the existing v0.2 planner.

    Only normal loading weeks are boosted. Recovery, taper and race weeks remain
    unchanged, and all user/automatic ceilings remain binding.
    """
    if getattr(training_module, "_v023_aggressiveness_installed", False):
        return

    original_weekly_target = training_module.weekly_target
    original_auto_max = training_module.science_auto_max

    def boosted_auto_max(c, race=None, ref=None, readiness=None):
        cap = float(original_auto_max(c, race, ref, readiness))
        if semantic_profile(c) == VERY_PROGRESSIVE:
            cap *= 1.0 + EXTRA_WEEKLY_TARGET
        return round(max(14.0, min(180.0, cap)), 1)

    def boosted_weekly_target(c, race, ws, readiness):
        target, phase = original_weekly_target(c, race, ws, readiness)
        if semantic_profile(c) != VERY_PROGRESSIVE:
            return target, phase
        if phase in {TrainingPhase.RECOVERY, TrainingPhase.TAPER, TrainingPhase.RACE}:
            return target, phase

        if get_setting(c, "max_weekly_km_mode", "auto") == "user":
            cap = float(get_setting(c, "max_weekly_km", 180.0) or 180.0)
        else:
            cap = boosted_auto_max(c, race, ws, readiness)

        boosted = float(target) * (1.0 + EXTRA_WEEKLY_TARGET)
        return round(max(14.0, min(boosted, cap)), 1), phase

    training_module.science_auto_max = boosted_auto_max
    training_module.weekly_target = boosted_weekly_target
    training_module._v023_aggressiveness_installed = True
