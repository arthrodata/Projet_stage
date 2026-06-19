from __future__ import annotations

import json
from typing import Any

from Backend.app.utils.database import iter_connection
from Backend.app.utils.row_normalization import normalize_rows


def remember_search(
    user: dict[str, Any] | None,
    *,
    source: str,
    params: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    if not isinstance(user, dict) or not user.get("id"):
        return

    safe_rows = normalize_rows(rows or [])
    with iter_connection() as conn:
        conn.execute(
            """
            INSERT INTO search_history (user_id, source, params_json, result_count, results_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(user["id"]),
                source,
                json.dumps(params, ensure_ascii=False),
                len(safe_rows),
                json.dumps(safe_rows, ensure_ascii=False),
            ),
        )


def list_search_history(user: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit or 10), 50))
    with iter_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, source, params_json, result_count, results_json, created_at
            FROM search_history
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (int(user["id"]), safe_limit),
        ).fetchall()

    history: list[dict[str, Any]] = []
    for row in rows:
        history.append(
            {
                "id": row["id"],
                "source": row["source"],
                "params": json.loads(row["params_json"] or "{}"),
                "result_count": row["result_count"],
                "data": json.loads(row["results_json"] or "[]"),
                "created_at": row["created_at"],
                "savedAt": row["created_at"],
            }
        )
    return history
