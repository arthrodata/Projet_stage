from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi.responses import FileResponse

from Backend.app.utils.row_normalization import CSV_EXPORT_COLUMNS, normalize_rows


def _meta_path(csv_path: Path) -> Path:
    return csv_path.with_name(f"{csv_path.name}.meta.json")


def _normalize_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def export_signature(source: str, **params: Any) -> dict[str, str]:
    return {
        "source": _normalize_value(source),
        **{key: _normalize_value(value) for key, value in sorted(params.items())},
    }


def cached_export_matches(csv_path: Path, signature: dict[str, str]) -> bool:
    if not csv_path.exists() or csv_path.stat().st_size <= 0:
        return False

    meta_path = _meta_path(csv_path)
    if not meta_path.exists():
        return False

    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    return payload.get("signature") == signature


def remember_export(csv_path: Path, signature: dict[str, str]) -> None:
    if not csv_path.exists() or csv_path.stat().st_size <= 0:
        return

    meta_path = _meta_path(csv_path)
    payload = {
        "signature": signature,
        "filename": csv_path.name,
        "size": csv_path.stat().st_size,
    }
    try:
        meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return


def write_rows_export(csv_path: Path, rows: list[dict[str, Any]], signature: dict[str, str]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(normalize_rows(rows or [], columns=CSV_EXPORT_COLUMNS)).reindex(columns=CSV_EXPORT_COLUMNS).to_csv(
        csv_path,
        index=False,
        encoding="utf-8-sig",
    )
    remember_export(csv_path, signature)


def csv_file_response(csv_path: Path, filename: str) -> FileResponse:
    size = csv_path.stat().st_size if csv_path.exists() else 0
    return FileResponse(
        path=str(csv_path),
        media_type="text/csv; charset=utf-8",
        filename=filename,
        headers={
            "Cache-Control": "no-store",
            "Content-Length": str(size),
            "Access-Control-Expose-Headers": "Content-Length",
        },
    )
