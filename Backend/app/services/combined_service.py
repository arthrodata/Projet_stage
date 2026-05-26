from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from Backend.app.services.gbif_service import search_gbif
from Backend.app.services.silene_expert_service import search_silene_expert_mapped


COMBINED_EXPORT_FILE = Path(__file__).resolve().parents[2] / "exports" / "resultats_gbif_silene.csv"
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
    "status",
]


def _normalize_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows or [])
    if df.empty:
        return pd.DataFrame(
            columns=[
                "source_bdd",
                "country",
                "coordinates",
                "eventDate",
                "basisOfRecord",
                "datasetName",
                "family",
                "genus",
                "species",
                "status",
                "iucn_status",
                "iucn_lookup_status",
                "iucn_assessment_id",
                "iucn_year",
                "iucn_scope",
                "redListCategory",
            ]
        )

    if "status" not in df.columns:
        if "iucn_status" in df.columns:
            df["status"] = df["iucn_status"]
        elif "redListCategory" in df.columns:
            df["status"] = df["redListCategory"]
        else:
            df["status"] = ""

    if "iucn_status" not in df.columns:
        df["iucn_status"] = ""
    if "iucn_lookup_status" not in df.columns:
        df["iucn_lookup_status"] = ""
    if "iucn_assessment_id" not in df.columns:
        df["iucn_assessment_id"] = ""
    if "iucn_year" not in df.columns:
        df["iucn_year"] = ""
    if "iucn_scope" not in df.columns:
        df["iucn_scope"] = ""
    if "redListCategory" not in df.columns:
        df["redListCategory"] = ""

    for col in (
        "source_bdd",
        "country",
        "coordinates",
        "eventDate",
        "basisOfRecord",
        "datasetName",
        "family",
        "genus",
        "species",
    ):
        if col not in df.columns:
            df[col] = ""

    # Normalisation type/string
    for col in df.columns:
        df[col] = df[col].fillna("").astype(str)

    ordered_cols = [
        "source_bdd",
        "country",
        "coordinates",
        "eventDate",
        "basisOfRecord",
        "datasetName",
        "family",
        "genus",
        "species",
        "status",
        "iucn_status",
        "iucn_lookup_status",
        "iucn_assessment_id",
        "iucn_year",
        "iucn_scope",
        "redListCategory",
    ]
    return df.reindex(columns=ordered_cols)


def search_gbif_and_silene_expert(
    family: Optional[str] = None,
    genus: Optional[str] = None,
    species: Optional[str] = None,
    country: Optional[str] = None,
    limit: int = 100,
    page: int = 1,
    *,
    export_csv: bool = True,
    export_file: Path | None = None,
    fetch_all: bool = False,
    include_iucn: bool = True,
    max_pages: int | None = None,
) -> list[dict[str, Any]]:
    """
    Recherche GBIF + Silene Expert en parallele et exporte UN SEUL CSV.
    """
    effective_export_file = export_file or COMBINED_EXPORT_FILE

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_gbif = executor.submit(
            search_gbif,
            family=family,
            genus=genus,
            species=species,
            country=country,
            export_csv=False,
            fetch_all=fetch_all,
            include_iucn=include_iucn,
            max_pages=max_pages,
        )
        f_silene = executor.submit(
            search_silene_expert_mapped,
            family=family,
            genus=genus,
            species=species,
            country=country,
            limit=limit,
            page=1 if fetch_all else page,
            export_csv=False,
            fetch_all=fetch_all,
            include_iucn=include_iucn,
            max_pages=max_pages,
        )

        gbif_rows = f_gbif.result()
        silene_rows = f_silene.result()

    combined = (gbif_rows or []) + (silene_rows or [])

    if export_csv:
        df = pd.concat([_normalize_rows(gbif_rows), _normalize_rows(silene_rows)], ignore_index=True)
        effective_export_file.parent.mkdir(parents=True, exist_ok=True)
        df.reindex(columns=CSV_EXPORT_COLUMNS).to_csv(
            effective_export_file,
            index=False,
            encoding="utf-8-sig",
        )

    return combined
