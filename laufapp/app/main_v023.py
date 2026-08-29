"""Laufapp v0.2.3 entry point.

Keep the tested v0.2.2 stack intact and add one backward-compatible fourth
planning-aggressiveness level.  No schema migration is required.
"""

from typing import Literal

from pydantic import BaseModel

import main_v022 as previous
from db import db_conn
from training_aggressiveness_v023 import (
    EXTRA_WEEKLY_TARGET,
    VERY_PROGRESSIVE,
    extra_weekly_target_fraction,
    install,
    semantic_profile,
    set_semantic_profile,
)

APP_VERSION = "0.2.3"

# Propagate release metadata through the compatibility stack.
previous.APP_VERSION = APP_VERSION
previous.previous.APP_VERSION = APP_VERSION
previous.previous.previous.APP_VERSION = APP_VERSION
core = previous.previous.previous
core.db_module.APP_VERSION = APP_VERSION
core.legacy.APP_VERSION = APP_VERSION
core.legacy.app.version = APP_VERSION
core.training.VERSION = APP_VERSION

app = previous.app
install(core.training)

# Extend the existing settings response additively.  The legacy three-value
# training_volume_profile remains valid for old clients; the semantic field is
# authoritative for the new four-level UI.
_original_settings_dict = core.legacy.settings_dict


def _settings_dict_v023(c):
    out = _original_settings_dict(c)
    out["training_aggressiveness_level"] = semantic_profile(c)
    out["training_volume_boost_pct"] = round(extra_weekly_target_fraction(c) * 100.0, 1)
    return out


core.legacy.settings_dict = _settings_dict_v023


class AggressivenessPayload(BaseModel):
    training_volume_profile: Literal[
        "gradual", "steady", "progressive", "very_progressive"
    ]


@app.get("/api/v2/settings/aggressiveness")
def api_v2_aggressiveness_get():
    with db_conn() as c:
        level = semantic_profile(c)
        return {
            "training_volume_profile": level,
            "extra_weekly_target_pct": round(
                EXTRA_WEEKLY_TARGET * 100.0 if level == VERY_PROGRESSIVE else 0.0, 1
            ),
        }


@app.patch("/api/v2/settings/aggressiveness")
def api_v2_aggressiveness_set(p: AggressivenessPayload):
    with db_conn() as c:
        set_semantic_profile(c, p.training_volume_profile)
        core.legacy.mark_plan_stale(c, "Planungsaggressivität geändert")
        return {"ok": True, "settings": _settings_dict_v023(c)}
