from __future__ import annotations

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


def _active_energy_series_kcal(workout: dict[str, Any]) -> float | None:
    values = workout.get("activeEnergy")
    if not isinstance(values, list) or not values:
        return None
    total = 0.0
    seen = False
    for item in values:
        if not isinstance(item, dict) or item.get("qty") is None:
            continue
        converted = _energy_item_kcal(item)
        # Never aggregate only a subset of an energy series: a mixed/unknown
        # unit would silently understate calories.  In that case leave the
        # legacy parser untouched instead of inventing a value.
        if converted is None:
            return None
        total += converted
        seen = True
    return total if seen else None


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


def ingest(c, payload: dict[str, Any], training) -> dict[str, Any]:
    return previous.ingest(c, prepare_real_hae_payload(payload), training)
