import logging

from fastapi import APIRouter, Depends, HTTPException
from typing import Any
from Backend.app.utils.date_filters import parse_query_date_range
from Backend.app.utils.csv_export_cache import (
    cached_export_matches,
    csv_file_response,
    export_signature,
    remember_export,
    write_rows_export,
)
from Backend.app.utils.auth import optional_current_user
from Backend.app.utils.history import remember_search
from Backend.app.utils.request_debug import log_endpoint_result, params_hash

from Backend.app.services.silene_expert_service import (
    EXPORT_FILE,
    diagnose_silene_expert,
    search_silene_expert,
    search_silene_expert_mapped,
)

router = APIRouter(prefix="/silene-expert", tags=["silene-expert"])
PREVIEW_EXPORT_FILE = EXPORT_FILE.with_name("silene_expert_preview_results.csv")
logger = logging.getLogger(__name__)


@router.get("/status")
def status():
    return diagnose_silene_expert()


@router.post("/synthese")
def synthese_for_web(payload: dict | None = None):
    # Le front Silene utilise POST /api/synthese/for_web.
    # Ici on expose un endpoint similaire via notre backend.
    return search_silene_expert(payload=payload or {})


@router.get("/synthese")
def synthese_for_web_get():
    # Pratique pour tester dans un navigateur (une URL ouverte fait un GET).
    return search_silene_expert(payload={})


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
    debug_params = {
        "family": family,
        "genus": genus,
        "species": species,
        "country": country,
        "date_from": date_from,
        "date_to": date_to,
        "limit": limit,
        "page": page,
        "fetch_all": False,
    }
    data = search_silene_expert_mapped(
        family=family,
        genus=genus,
        species=species,
        country=country,
        date_from=start_date,
        date_to=end_date,
        limit=limit,
        page=page,
        export_csv=False,
    )
    log_endpoint_result(logger, endpoint="/silene-expert/search", user=user, params=debug_params, rows=data)
    write_rows_export(
        PREVIEW_EXPORT_FILE,
        data,
        export_signature(
            "silene_expert_search",
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
        source="silene_expert",
        params={
            "source": "silene_expert",
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
    limit: int = 200,
    max_pages: int | None = None,
    refresh: str | None = None,
):
    if not any([(family or "").strip(), (genus or "").strip(), (species or "").strip()]):
        raise HTTPException(
            status_code=400,
            detail="To export a Silene Expert CSV, enter at least one taxonomic filter (family/genus/species).",
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
        "limit": limit,
        "max_pages": max_pages,
        "fetch_all": True,
    }
    signature = export_signature(
        "silene_expert",
        family=family,
        genus=genus,
        species=species,
        country=country,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        max_pages=max_pages,
    )
    if refresh or not cached_export_matches(EXPORT_FILE, signature):
        rows = search_silene_expert_mapped(
            family=family,
            genus=genus,
            species=species,
            country=country,
            date_from=start_date,
            date_to=end_date,
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
            endpoint="/silene-expert/search/csv",
            user=None,
            params=debug_params,
            rows=rows,
            extra={"cache": "miss"},
        )
    else:
        logger.info(
            "request_debug endpoint=/silene-expert/search/csv user=anonymous params_hash=%s params=%s cache=hit file=%s",
            params_hash(debug_params),
            signature,
            EXPORT_FILE,
        )

    return csv_file_response(EXPORT_FILE, "silene_expert_results.csv")
