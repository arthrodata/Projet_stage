from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

import pandas as pd

from Backend.app.utils.date_filters import parse_any_date


MISSING_VALUE = "Non renseigne"
STANDARD_COLUMNS = [
    "source_bdd",
    "country",
    "coordinates",
    "eventDate",
    "basisOfRecord",
    "datasetName",
    "family",
    "genus",
    "species",
    "quality_grade",
    "status",
    "iucn_status",
    "iucn_lookup_status",
    "iucn_assessment_id",
    "iucn_year",
    "iucn_scope",
    "redListCategory",
]
CSV_EXPORT_COLUMNS = [
    "source_bdd",
    "country",
    "coordinates",
    "eventDate",
    "basisOfRecord",
    "datasetName",
    "family",
    "genus",
    "species",
    "quality_grade",
    "status",
]


def clean_text(value: Any, *, missing: str = MISSING_VALUE) -> str:
    if value is None:
        return missing
    if isinstance(value, float) and pd.isna(value):
        return missing
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "null", "not provided"}:
        return missing
    return text


def normalize_event_date(value: Any) -> str:
    parsed = parse_any_date(value)
    return parsed.isoformat() if parsed else MISSING_VALUE


def _decimal_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", ".")
    try:
        decimal_value = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    normalized = format(decimal_value.quantize(Decimal("0.000001")), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def normalize_coordinates(value: Any) -> str:
    if value is None:
        return MISSING_VALUE
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "null", "not provided", "non renseigne"}:
        return MISSING_VALUE

    normalized = text.replace(";", ",")
    parts = [part.strip() for part in normalized.split(",") if part.strip()]
    if len(parts) < 2:
        return MISSING_VALUE

    lat = _decimal_text(parts[0])
    lon = _decimal_text(parts[1])
    if lat is None or lon is None:
        return MISSING_VALUE
    return f"{lat}, {lon}"


def normalize_row(row: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for column in STANDARD_COLUMNS:
        value = row.get(column)
        if column == "eventDate":
            normalized[column] = normalize_event_date(value)
        elif column == "coordinates":
            normalized[column] = normalize_coordinates(value)
        elif column in {"iucn_assessment_id", "iucn_year", "iucn_scope", "iucn_lookup_status", "redListCategory"}:
            normalized[column] = clean_text(value, missing="")
        elif column == "quality_grade":
            normalized[column] = clean_text(value, missing="")
        else:
            normalized[column] = clean_text(value)

    if not normalized["status"] or normalized["status"] == MISSING_VALUE:
        normalized["status"] = normalized["iucn_status"] or MISSING_VALUE
    if not normalized["redListCategory"]:
        normalized["redListCategory"] = normalized["iucn_status"]
    return normalized


def normalize_rows(rows: Iterable[dict[str, Any]], *, columns: list[str] | None = None) -> list[dict[str, str]]:
    selected_columns = columns or STANDARD_COLUMNS
    return [
        {column: normalized.get(column, MISSING_VALUE) for column in selected_columns}
        for normalized in (normalize_row(row) for row in rows)
    ]


def normalize_dataframe(df: pd.DataFrame, *, columns: list[str] | None = None) -> pd.DataFrame:
    selected_columns = columns or STANDARD_COLUMNS
    if df.empty:
        return pd.DataFrame(columns=selected_columns)
    rows = normalize_rows(df.to_dict(orient="records"), columns=selected_columns)
    return pd.DataFrame(rows).reindex(columns=selected_columns)
