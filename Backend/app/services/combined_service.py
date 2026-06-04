from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from Backend.app.services.gbif_service import search_gbif
from Backend.app.services.inaturalist_service import search_inaturalist
from Backend.app.services.silene_expert_service import search_silene_expert_mapped
from Backend.app.utils.row_normalization import CSV_EXPORT_COLUMNS, STANDARD_COLUMNS, normalize_dataframe, normalize_rows


COMBINED_EXPORT_FILE = Path(__file__).resolve().parents[2] / "exports" / "resultats_gbif_silene_inaturalist.csv"
def _normalize_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows or [])
    if df.empty:
        return pd.DataFrame(columns=STANDARD_COLUMNS)
    return normalize_dataframe(df, columns=STANDARD_COLUMNS)


def search_gbif_and_silene_expert(
    family: Optional[str] = None,
    genus: Optional[str] = None,
    species: Optional[str] = None,
    country: Optional[str] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    quality_grade: str | None = None,
    limit: int = 100,
    page: int = 1,
    *,
    export_csv: bool = True,
    export_file: Path | None = None,
    fetch_all: bool = False,
    include_iucn: bool = True,
    max_pages: int | None = None,
    max_records: int | None = None,
) -> list[dict[str, Any]]:
    """
    Recherche GBIF + Silene Expert + iNaturalist en parallele et exporte UN SEUL CSV.
    """
    effective_export_file = export_file or COMBINED_EXPORT_FILE

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_gbif = executor.submit(
            search_gbif,
            family=family,
            genus=genus,
            species=species,
            country=country,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            export_csv=False,
            fetch_all=fetch_all,
            include_iucn=include_iucn,
            max_pages=max_pages,
            max_records=max_records,
        )
        f_silene = executor.submit(
            search_silene_expert_mapped,
            family=family,
            genus=genus,
            species=species,
            country=country,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            page=1 if fetch_all else page,
            export_csv=False,
            fetch_all=fetch_all,
            include_iucn=include_iucn,
            max_pages=max_pages,
            max_records=max_records,
        )
        f_inaturalist = executor.submit(
            search_inaturalist,
            family=family,
            genus=genus,
            species=species,
            country=country,
            date_from=date_from,
            date_to=date_to,
            quality_grade=quality_grade,
            limit=limit,
            page=1 if fetch_all else page,
            export_csv=False,
            fetch_all=fetch_all,
            include_iucn=include_iucn,
            max_pages=max_pages,
            max_records=max_records,
        )

        gbif_rows = f_gbif.result()
        silene_rows = f_silene.result()
        inaturalist_rows = f_inaturalist.result()

    combined = normalize_rows((gbif_rows or []) + (silene_rows or []) + (inaturalist_rows or []))

    if export_csv:
        df = pd.concat(
            [_normalize_rows(gbif_rows), _normalize_rows(silene_rows), _normalize_rows(inaturalist_rows)],
            ignore_index=True,
        )
        effective_export_file.parent.mkdir(parents=True, exist_ok=True)
        df.reindex(columns=CSV_EXPORT_COLUMNS).to_csv(
            effective_export_file,
            index=False,
            encoding="utf-8-sig",
        )

    return combined
