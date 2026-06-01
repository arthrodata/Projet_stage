from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Optional, Tuple, TypeVar


def parse_iso_date(value: str | None) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None
    return date.fromisoformat(raw)


def parse_query_date_range(date_from: str | None, date_to: str | None) -> tuple[date | None, date | None]:
    """
    Parse des paramètres query YYYY-MM-DD.
    Lève ValueError si format invalide ou si date_from > date_to.
    """
    start = parse_iso_date(date_from)
    end = parse_iso_date(date_to)
    if start and end and start > end:
        raise ValueError("date_from must be <= date_to")
    return start, end


def parse_any_date(value: Any) -> date | None:
    """
    Parse une date venant de sources externes.
    Accepte typiquement: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, DD/MM/YYYY, MM/DD/YYYY.
    Retourne None si non parsable.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"non renseigne", "not provided", "none", "null"}:
        return None

    # Strip time part if present (ISO 8601)
    if "T" in text and len(text) >= 10:
        text = text.split("T", 1)[0].strip()

    # Some APIs can return ranges; keep the first date token.
    for sep in ("/", " - ", ",", ";", "|"):
        if sep in text and len(text) > 10:
            candidate = text.split(sep, 1)[0].strip()
            if candidate:
                text = candidate
                break

    # ISO date
    try:
        if len(text) >= 10:
            return date.fromisoformat(text[:10])
        return date.fromisoformat(text)
    except Exception:
        pass

    # Common human formats
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            continue

    return None


T = TypeVar("T", bound=dict)


def filter_rows_by_date_range(
    rows: Iterable[T],
    *,
    date_from: date | None,
    date_to: date | None,
    field: str = "eventDate",
    keep_unparseable: bool = False,
) -> list[T]:
    if not date_from and not date_to:
        return list(rows)

    out: list[T] = []
    for row in rows:
        value = row.get(field) if isinstance(row, dict) else None
        d = parse_any_date(value)
        if d is None:
            if keep_unparseable:
                out.append(row)
            continue
        if date_from and d < date_from:
            continue
        if date_to and d > date_to:
            continue
        out.append(row)
    return out

