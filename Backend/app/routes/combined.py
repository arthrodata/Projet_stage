from fastapi import APIRouter, Depends, HTTPException
from typing import Any
from Backend.app.utils.csv_export_cache import (
    cached_export_matches,
    csv_file_response,
    export_signature,
    remember_export,
    write_rows_export,
)
from Backend.app.utils.date_filters import parse_query_date_range

from Backend.app.services.combined_service import COMBINED_EXPORT_FILE, search_gbif_and_silene_expert
from Backend.app.utils.auth import optional_current_user
from Backend.app.utils.history import remember_search

router = APIRouter(prefix="/combined", tags=["combined"])


@router.get("/search")
def search(
    family: str = None,
    genus: str = None,
    species: str = None,
    country: str = None,
    date_from: str = None,
    date_to: str = None,
    quality_grade: str = None,
    limit: int = 100,
    page: int = 1,
    user: dict[str, Any] | None = Depends(optional_current_user),
):
    try:
        start_date, end_date = parse_query_date_range(date_from, date_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="date_from/date_to must be YYYY-MM-DD and date_from <= date_to.")
    data = search_gbif_and_silene_expert(
        family=family,
        genus=genus,
        species=species,
        country=country,
        date_from=start_date,
        date_to=end_date,
        quality_grade=quality_grade,
        limit=limit,
        page=page,
        export_csv=False,
    )
    write_rows_export(
        COMBINED_EXPORT_FILE,
        data,
        export_signature(
            "combined_search",
            family=family,
            genus=genus,
            species=species,
            country=country,
            date_from=date_from,
            date_to=date_to,
            quality_grade=quality_grade,
            limit=limit,
            page=page,
        ),
    )
    remember_search(
        user,
        source="both",
        params={
            "source": "both",
            "family": family,
            "genus": genus,
            "species": species,
            "country": country,
            "dateFrom": date_from,
            "dateTo": date_to,
            "qualityGrade": quality_grade,
            "resultLimit": limit,
        },
        rows=data,
    )
    return data


@router.get("/search/csv")
def export_csv(
    family: str = None,
    genus: str = None,
    species: str = None,
    country: str = None,
    date_from: str = None,
    date_to: str = None,
    quality_grade: str = None,
    limit: int = 200,
    max_pages: int | None = None,
    refresh: str | None = None,
):
    if not any([(family or "").strip(), (genus or "").strip(), (species or "").strip()]):
        raise HTTPException(
            status_code=400,
            detail="Pour exporter un CSV combine, renseigner au moins un filtre taxonomique (family/genus/species).",
        )
    try:
        start_date, end_date = parse_query_date_range(date_from, date_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="date_from/date_to must be YYYY-MM-DD and date_from <= date_to.")

    signature = export_signature(
        "combined",
        family=family,
        genus=genus,
        species=species,
        country=country,
        date_from=date_from,
        date_to=date_to,
        quality_grade=quality_grade,
        limit=limit,
        max_pages=max_pages,
    )
    if refresh or not cached_export_matches(COMBINED_EXPORT_FILE, signature):
        search_gbif_and_silene_expert(
            family=family,
            genus=genus,
            species=species,
            country=country,
            date_from=start_date,
            date_to=end_date,
            quality_grade=quality_grade,
            limit=limit,
            page=1,
            fetch_all=True,
            include_iucn=True,
            max_pages=max_pages,
            export_csv=True,
            export_file=COMBINED_EXPORT_FILE,
        )
        remember_export(COMBINED_EXPORT_FILE, signature)

    return csv_file_response(COMBINED_EXPORT_FILE, "resultats_gbif_silene_inaturalist.csv")
