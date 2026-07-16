import logging

from fastapi import APIRouter, Depends, HTTPException
from typing import Any
from Backend.app.services.inaturalist_service import EXPORT_FILE, search_inaturalist
from Backend.app.utils.csv_export_cache import (
    cached_export_matches,
    csv_file_response,
    export_signature,
    remember_export,
    write_rows_export,
)
from Backend.app.utils.auth import optional_current_user
from Backend.app.utils.history import remember_search
from Backend.app.utils.date_filters import parse_query_date_range
from Backend.app.utils.request_debug import log_endpoint_result, params_hash


router = APIRouter(prefix="/inaturalist", tags=["inaturalist"])
PREVIEW_EXPORT_FILE = EXPORT_FILE.with_name("inaturalist_preview_results.csv")
logger = logging.getLogger(__name__)


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

    debug_params = {
        "family": family,
        "genus": genus,
        "species": species,
        "country": country,
        "date_from": date_from,
        "date_to": date_to,
        "quality_grade": quality_grade,
        "limit": limit,
        "page": page,
        "fetch_all": False,
    }
    data = search_inaturalist(
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
    log_endpoint_result(logger, endpoint="/inaturalist/search", user=user, params=debug_params, rows=data)
    write_rows_export(
        PREVIEW_EXPORT_FILE,
        data,
        export_signature(
            "inaturalist_search",
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
        source="inaturalist",
        params={
            "source": "inaturalist",
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
            detail="To export an iNaturalist CSV, enter at least one taxonomic filter (family/genus/species).",
        )
    try:
        start_date, end_date = parse_query_date_range(date_from, date_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="date_from/date_to must be YYYY-MM-DD and date_from <= date_to.")

    debug_params = {
        "family": family,
        "genus": genus,
        "species": species,
        "country": country,
        "date_from": date_from,
        "date_to": date_to,
        "quality_grade": quality_grade,
        "limit": limit,
        "max_pages": max_pages,
        "fetch_all": True,
    }
    signature = export_signature(
        "inaturalist",
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
    if refresh or not cached_export_matches(EXPORT_FILE, signature):
        rows = search_inaturalist(
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
            export_file=EXPORT_FILE,
        )
        remember_export(EXPORT_FILE, signature)
        log_endpoint_result(
            logger,
            endpoint="/inaturalist/search/csv",
            user=None,
            params=debug_params,
            rows=rows,
            extra={"cache": "miss"},
        )
    else:
        logger.info(
            "request_debug endpoint=/inaturalist/search/csv user=anonymous params_hash=%s params=%s cache=hit file=%s",
            params_hash(debug_params),
            signature,
            EXPORT_FILE,
        )

    return csv_file_response(EXPORT_FILE, "inaturalist_results.csv")
