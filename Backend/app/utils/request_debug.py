from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime
from typing import Any


def _jsonable(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def params_hash(params: dict[str, Any]) -> str:
    payload = json.dumps(_jsonable(params), sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def user_debug_id(user: dict[str, Any] | None) -> str:
    if not isinstance(user, dict):
        return "anonymous"
    user_id = user.get("id", "")
    email = user.get("email", "")
    return f"id={user_id} email={email}".strip()


def event_date_bounds(rows: list[dict[str, Any]] | None) -> tuple[str, str]:
    if not isinstance(rows, list):
        return "", ""
    values = [
        str(row.get("eventDate") or "").strip()
        for row in (rows or [])
        if isinstance(row, dict)
    ]
    values = [value for value in values if value and value != "Non renseigne"]
    if not values:
        return "", ""
    return values[0], values[-1]


def log_endpoint_result(
    logger: logging.Logger,
    *,
    endpoint: str,
    user: dict[str, Any] | None,
    params: dict[str, Any],
    rows: list[dict[str, Any]] | None,
    extra: dict[str, Any] | None = None,
) -> None:
    first_event_date, last_event_date = event_date_bounds(rows)
    safe_extra = extra or {}
    logger.info(
        "request_debug endpoint=%s user=%s params_hash=%s params=%s result_count=%s first_eventDate=%s last_eventDate=%s extra=%s",
        endpoint,
        user_debug_id(user),
        params_hash(params),
        json.dumps(_jsonable(params), sort_keys=True, ensure_ascii=False, default=str),
        len(rows) if isinstance(rows, list) else 0,
        first_event_date,
        last_event_date,
        json.dumps(_jsonable(safe_extra), sort_keys=True, ensure_ascii=False, default=str),
    )
