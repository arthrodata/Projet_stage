from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
import logging
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from Backend.app.services.iucn_service import IUCN_EMPTY_STATUS, get_iucn_enrichments
from Backend.app.services.gbif_service import search_gbif
from Backend.app.services.inaturalist_service import search_inaturalist
from Backend.app.services.silene_expert_service import search_silene_expert_mapped
from Backend.app.services.steli_service import search_steli
from Backend.app.utils.row_normalization import CSV_EXPORT_COLUMNS, STANDARD_COLUMNS, normalize_dataframe, normalize_rows


COMBINED_EXPORT_FILE = Path(__file__).resolve().parents[2] / "exports" / "resultats_gbif_silene_inaturalist.csv"
logger = logging.getLogger(__name__)


def _normalize_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows or [])
    if df.empty:
        return pd.DataFrame(columns=STANDARD_COLUMNS)
    return normalize_dataframe(df, columns=STANDARD_COLUMNS)


def _future_rows(source_name: str, future) -> list[dict[str, Any]]:
    try:
        rows = future.result()
    except Exception:
        logger.exception("Combined search source failed: %s", source_name)
        return []
    return rows or []


def _enrich_combined_iucn(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return rows

    species_names = [
        str(row.get("species") or "").strip()
        for row in rows
        if str(row.get("species") or "").strip()
        and str(row.get("species") or "").strip() != "Non renseigne"
    ]
    enrichments = get_iucn_enrichments(species_names)

    for row in rows:
        species_name = str(row.get("species") or "").strip()
        enrichment = enrichments.get(species_name, {})
        status = enrichment.get("iucn_status") or IUCN_EMPTY_STATUS
        row["iucn_status"] = status
        row["iucn_lookup_status"] = enrichment.get("iucn_lookup_status") or ""
        row["iucn_assessment_id"] = enrichment.get("iucn_assessment_id") or ""
        row["iucn_year"] = enrichment.get("iucn_year") or ""
        row["iucn_scope"] = enrichment.get("iucn_scope") or ""
        row["status"] = status
        row["redListCategory"] = status

    return rows


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
    Recherche GBIF + Silene Expert + iNaturalist + STELI en parallele et exporte UN SEUL CSV.
    """
    effective_export_file = export_file or COMBINED_EXPORT_FILE
    enrich_after_merge = bool(include_iucn)

    with ThreadPoolExecutor(max_workers=4) as executor:
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
            include_iucn=False if enrich_after_merge else include_iucn,
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
            include_iucn=False if enrich_after_merge else include_iucn,
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
            include_iucn=False if enrich_after_merge else include_iucn,
            max_pages=max_pages,
            max_records=max_records,
        )
        f_steli = executor.submit(
            search_steli,
            family=family,
            genus=genus,
            species=species,
            country=country,
            start_date=date_from,
            end_date=date_to,
            limit=limit,
            page=1 if fetch_all else page,
            export_csv=False,
            fetch_all=fetch_all,
            max_pages=max_pages,
            max_records=max_records,
            include_iucn=False if enrich_after_merge else include_iucn,
        )

        gbif_rows = _future_rows("GBIF", f_gbif)
        silene_rows = _future_rows("Silene Expert", f_silene)
        inaturalist_rows = _future_rows("iNaturalist", f_inaturalist)
        steli_rows = _future_rows("STELI", f_steli)

    if enrich_after_merge:
        all_rows = _enrich_combined_iucn((gbif_rows or []) + (silene_rows or []) + (inaturalist_rows or []) + (steli_rows or []))
        gbif_rows = [row for row in all_rows if row.get("source_bdd") == "GBIF"]
        silene_rows = [row for row in all_rows if row.get("source_bdd") == "Silene Expert"]
        inaturalist_rows = [row for row in all_rows if row.get("source_bdd") == "iNaturalist"]
        steli_rows = [row for row in all_rows if row.get("source_bdd") == "STELI"]

    combined = normalize_rows((gbif_rows or []) + (silene_rows or []) + (inaturalist_rows or []) + (steli_rows or []))

    if export_csv:
        df = pd.concat(
            [_normalize_rows(gbif_rows), _normalize_rows(silene_rows), _normalize_rows(inaturalist_rows), _normalize_rows(steli_rows)],
            ignore_index=True,
        )
        effective_export_file.parent.mkdir(parents=True, exist_ok=True)
        df.reindex(columns=CSV_EXPORT_COLUMNS).to_csv(
            effective_export_file,
            index=False,
            encoding="utf-8-sig",
        )

    return combined
