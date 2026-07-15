from fastapi import APIRouter, Depends, HTTPException
from typing import Any

from Backend.app.services.steli_service import EXPORT_FILE, search_steli
from Backend.app.utils.auth import optional_current_user
from Backend.app.utils.csv_export_cache import (
    cached_export_matches,
    csv_file_response,
    export_signature,
    remember_export,
    write_rows_export,
)
from Backend.app.utils.date_filters import parse_query_date_range
from Backend.app.utils.history import remember_search


router = APIRouter(prefix="/steli", tags=["steli"])


@router.get("/search")
def search(
    family: str = None,
    genus: str = None,
    species: str = None,
    country: str = None,
    date_from: str = None,
    date_to: str = None,
    limit: int = 100,
    page: int = 1,
    user: dict[str, Any] | None = Depends(optional_current_user),
):
    try:
        start_date, end_date = parse_query_date_range(date_from, date_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="date_from/date_to must be YYYY-MM-DD and date_from <= date_to.")

    data = search_steli(
        family=family,
        genus=genus,
        species=species,
        country=country,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        page=page,
        export_csv=False,
    )
    write_rows_export(
        EXPORT_FILE,
        data,
        export_signature(
            "steli_search",
            family=family,
            genus=genus,
            species=species,
            country=country,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            page=page,
        ),
    )
    remember_search(
        user,
        source="steli",
        params={
            "source": "steli",
            "family": family,
            "genus": genus,
            "species": species,
            "country": country,
            "dateFrom": date_from,
            "dateTo": date_to,
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
    limit: int = 300,
    max_pages: int | None = None,
    include_iucn: bool = False,
    refresh: str | None = None,
):
    try:
        start_date, end_date = parse_query_date_range(date_from, date_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="date_from/date_to must be YYYY-MM-DD and date_from <= date_to.")

    signature = export_signature(
        "steli",
        family=family,
        genus=genus,
        species=species,
        country=country,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        max_pages=max_pages,
        include_iucn=include_iucn,
    )
    if refresh or not cached_export_matches(EXPORT_FILE, signature):
        search_steli(
            family=family,
            genus=genus,
            species=species,
            country=country,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            page=1,
            fetch_all=True,
            max_pages=max_pages,
            include_iucn=include_iucn,
            export_csv=True,
            export_file=EXPORT_FILE,
        )
        remember_export(EXPORT_FILE, signature)

    return csv_file_response(EXPORT_FILE, "steli_results.csv")
