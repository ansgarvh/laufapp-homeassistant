"""Successful data-sync timestamp aggregation for Laufapp v0.2.22."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def _utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    elif "T" not in text and " " in text:
        # SQLite CURRENT_TIMESTAMP is stored as UTC without an explicit zone.
        text = f"{text.replace(' ', 'T', 1)}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _hae_timestamp(c) -> datetime | None:
    row = c.execute(
        "SELECT value FROM settings WHERE key='health_auto_export_last_sync'"
    ).fetchone()
    if not row:
        return None
    raw = row["value"]
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        value = raw
    return _utc_timestamp(value)


def _apple_health_import_timestamp(c) -> datetime | None:
    row = c.execute(
        "SELECT finished_at FROM import_jobs "
        "WHERE status='completed' AND finished_at IS NOT NULL "
        "ORDER BY finished_at DESC,id DESC LIMIT 1"
    ).fetchone()
    return _utc_timestamp(row["finished_at"]) if row else None


def last_successful_data_sync(c) -> dict[str, str] | None:
    """Return the newest completed HAE or Apple Health import in canonical UTC."""
    candidates: list[tuple[datetime, str]] = []
    if hae_at := _hae_timestamp(c):
        candidates.append((hae_at, "health_auto_export"))
    if imported_at := _apple_health_import_timestamp(c):
        candidates.append((imported_at, "apple_health_import"))
    if not candidates:
        return None
    synced_at, source = max(candidates, key=lambda item: item[0])
    return {
        "at": synced_at.isoformat().replace("+00:00", "Z"),
        "source": source,
    }
