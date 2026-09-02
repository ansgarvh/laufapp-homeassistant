from __future__ import annotations

import hashlib
import math
import re
from typing import Any

import health_auto_export_v027 as previous

MIN_TOKEN_LENGTH = previous.MIN_TOKEN_LENGTH
MAX_TOKEN_LENGTH = previous.MAX_TOKEN_LENGTH
MIN_UNIQUE_TOKEN_CHARS = previous.MIN_UNIQUE_TOKEN_CHARS
MAX_BODY_BYTES = previous.MAX_BODY_BYTES

# Real German Health Auto Export v2 payloads observed on 2026-08-27 and
# 2026-08-30 identify Apple running workouts as "Outdoor Ausführen".  Keep
# those exact HAE labels while retaining the previously supported English and
# German running names.  Generic "ausführen" is deliberately not matched as a
# substring to avoid classifying unrelated workout names as runs.
_RUNNING_EXACT_NAMES = {
    "run",
    "running",
    "lauf",
    "laufen",
    "outdoor run",
    "indoor run",
    "outdoor running",
    "indoor running",
    "outdoor lauf",
    "indoor lauf",
    "outdoor laufen",
    "indoor laufen",
    "outdoor ausführen",
    "indoor ausführen",
    "ausführen",
}
_RUNNING_WORD = re.compile(r"(?:^|[\s/_-])(run|running|lauf|laufen)(?:$|[\s/_-])")


def configured_token() -> str:
    return previous.configured_token()


def token_configuration_error() -> str | None:
    return previous.token_configuration_error()


def authorized(authorization: str | None, x_token: str | None) -> bool:
    return previous.authorized(authorization, x_token)


def _normalized_workout_name(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def is_running_workout(workout: dict[str, Any]) -> bool:
    name = _normalized_workout_name(workout.get("name"))
    return name in _RUNNING_EXACT_NAMES or bool(_RUNNING_WORD.search(name))


def _energy_item_kcal(item: Any) -> float | None:
    if not isinstance(item, dict) or item.get("qty") is None:
        return None
    try:
        qty = float(item["qty"])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(qty) or qty < 0:
        return None
    unit = str(item.get("units") or "").strip().casefold().replace(" ", "")
    if unit in {"kj", "kilojoule", "kilojoules"}:
        return qty / 4.184
    if unit in {"kcal", "kilocalorie", "kilocalories"}:
        return qty
    return None


def _energy_series_kcal(values: Any) -> float | None:
    if not isinstance(values, list) or not values:
        return None
    total = 0.0
    seen = False
    for item in values:
        if not isinstance(item, dict) or item.get("qty") is None:
            continue
        converted = _energy_item_kcal(item)
        # Never aggregate only a subset of an energy series: a mixed/unknown
        # unit would silently understate calories.
        if converted is None:
            return None
        total += converted
        seen = True
    return total if seen else None


def _active_energy_series_kcal(workout: dict[str, Any]) -> float | None:
    return _energy_series_kcal(workout.get("activeEnergy"))


def _total_energy_kcal(workout: dict[str, Any]) -> float | None:
    """Return HAE total workout energy without confusing it with active energy.

    Real HAE exports may provide ``totalEnergy`` either as a summary quantity or
    as a time series.  It contains basal/resting energy as well, which is exactly
    why it must remain a separate metric and must never replace runs.calories.
    """
    value = workout.get("totalEnergy")
    if isinstance(value, dict):
        return _energy_item_kcal(value)
    return _energy_series_kcal(value)


def prepare_real_hae_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize only real HAE variants that the v0.2.11 parser did not accept.

    The persistent schema, workout ID, official workout distance, duration,
    heart-rate samples, cadence and GPS route remain unchanged.  The old parser
    still performs all bounds checking, cross-source deduplication and inserts.
    """
    if not isinstance(payload, dict):
        return payload
    data = payload.get("data")
    if not isinstance(data, dict):
        return payload
    workouts = data.get("workouts")
    if not isinstance(workouts, list):
        return payload

    for workout in workouts:
        if not isinstance(workout, dict) or not is_running_workout(workout):
            continue

        # v0.2.6/v0.2.7 used a narrow English/German substring filter.  The
        # normalized name is not persisted; setting it to Running merely lets
        # the already-tested importer process the real localized HAE workout.
        workout["name"] = "Running"

        # Prefer HAE's explicit ActiveEnergyBurned summary when it exists.  The
        # long real-world sample omits that summary but contains a per-second
        # activeEnergy series.  Summing that series is appropriate; totalEnergy
        # additionally contains basal energy and must not be substituted for it.
        if not isinstance(workout.get("activeEnergyBurned"), dict):
            kcal = _active_energy_series_kcal(workout)
            if kcal is not None:
                workout["activeEnergyBurned"] = {"qty": kcal, "units": "kcal"}

    return payload


def _store_total_energy_samples(c, payload: dict[str, Any]) -> int:
    """Persist optional HAE total energy additively in the existing sample table."""
    data = payload.get("data") if isinstance(payload, dict) else None
    workouts = data.get("workouts") if isinstance(data, dict) else None
    if not isinstance(workouts, list):
        return 0
    added = 0
    for workout in workouts:
        if not isinstance(workout, dict) or not is_running_workout(workout):
            continue
        workout_id = str(workout.get("id") or "").strip()
        total_kcal = _total_energy_kcal(workout)
        if not workout_id or total_kcal is None:
            continue
        run = c.execute("SELECT id,started_at FROM runs WHERE external_id=?", (workout_id,)).fetchone()
        if not run:
            continue
        external_id = "hae:" + hashlib.sha256(
            f"workout|{workout_id}|total_calories".encode("utf-8")
        ).hexdigest()
        existing = c.execute(
            "SELECT id,value FROM run_samples WHERE external_id=?", (external_id,)
        ).fetchone()
        if existing:
            if abs(float(existing["value"]) - total_kcal) > 1e-9:
                c.execute(
                    "UPDATE run_samples SET value=?,unit='kcal',sampled_at=?,source='health_auto_export' WHERE id=?",
                    (total_kcal, str(run["started_at"]), int(existing["id"])),
                )
            continue
        c.execute(
            "INSERT INTO run_samples(external_id,run_id,metric_type,sampled_at,value,unit,source) VALUES(?,?,?,?,?,'kcal','health_auto_export')",
            (external_id, int(run["id"]), "total_calories", str(run["started_at"]), total_kcal),
        )
        added += 1
    return added


def ingest(c, payload: dict[str, Any], training) -> dict[str, Any]:
    prepared = prepare_real_hae_payload(payload)
    result = previous.ingest(c, prepared, training)
    extra = _store_total_energy_samples(c, prepared)
    if extra and isinstance(result, dict):
        result["samples_added"] = int(result.get("samples_added", 0)) + extra
    return result
