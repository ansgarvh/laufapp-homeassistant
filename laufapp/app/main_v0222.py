"""Laufapp v0.2.22 calendar guardrails and successful-sync status.

This composition layer preserves the complete v0.2.21 icon, Health Auto
Export, Apple Health, Ingress, relay and persistence behavior. It adds a
conservative calendar optimiser plus the latest successful data-sync timestamp.
"""
from __future__ import annotations

import main_v0221 as previous
from data_sync_v0222 import last_successful_data_sync
from training_calendar_guardrails_v0222 import (
    calendar_rule_report,
    enforce_calendar_rules,
)

APP_VERSION = "0.2.22"

_module = previous
for _ in range(40):
    if _module is None:
        break
    if hasattr(_module, "APP_VERSION"):
        _module.APP_VERSION = APP_VERSION
    _module = getattr(_module, "previous", None)

core = previous.core
core.db_module.APP_VERSION = APP_VERSION
core.legacy.APP_VERSION = APP_VERSION
core.legacy.app.version = APP_VERSION
core.training.VERSION = APP_VERSION

process_health_auto_export_request = previous.process_health_auto_export_request
app = previous.app

_previous_generate_week = core.training.generate_week


def _calendar_guarded_generate_week(c, ws=None, force=False):
    generated = _previous_generate_week(c, ws, force)
    return enforce_calendar_rules(c, generated)


# training_v020.week_summary resolves its module-level generate_week dynamically.
# Keep compatibility and coach exports aligned so every caller uses the guard.
core.training.generate_week = _calendar_guarded_generate_week
core.legacy.generate_week = _calendar_guarded_generate_week
if hasattr(core.coach_module, "generate_week"):
    core.coach_module.generate_week = _calendar_guarded_generate_week

_previous_science_guardrails = core.training._science_guardrails


def _science_guardrails_v0222(c, workouts, ws):
    out = _previous_science_guardrails(c, workouts, ws)
    calendar = calendar_rule_report(c, workouts)
    out["calendar_spacing"] = {
        key: value for key, value in calendar.items() if key != "alerts"
    }
    if calendar["alerts"]:
        out.setdefault("alerts", []).extend(calendar["alerts"])
        out["needs_review"] = True
    return out


core.training._science_guardrails = _science_guardrails_v0222

_previous_dashboard = core.legacy.dashboard


def _dashboard_v0222(c):
    dashboard = _previous_dashboard(c)
    dashboard["data_sync"] = last_successful_data_sync(c)
    return dashboard


# main.py's established /api/dashboard route resolves this global dynamically.
# Keep the active planner export aligned for direct internal callers as well.
core.legacy.dashboard = _dashboard_v0222
core.training.dashboard = _dashboard_v0222
