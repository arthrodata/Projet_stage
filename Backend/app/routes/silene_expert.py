from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from Backend.app.utils.date_filters import parse_query_date_range
from Backend.app.utils.csv_export_cache import cached_export_matches, export_signature, remember_export, write_rows_export

from Backend.app.services.silene_expert_service import (
    EXPORT_FILE,
    search_silene_expert,
    search_silene_expert_mapped,
)

router = APIRouter(prefix="/silene-expert", tags=["silene-expert"])


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
):
    try:
        start_date, end_date = parse_query_date_range(date_from, date_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="date_from/date_to must be YYYY-MM-DD and date_from <= date_to.")
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
    write_rows_export(
        EXPORT_FILE,
        data,
        export_signature(
            "silene_expert_preview",
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
    max_pages: int = 50,
):
    if not any([(family or "").strip(), (genus or "").strip(), (species or "").strip()]):
        raise HTTPException(
            status_code=400,
            detail="Pour exporter un CSV Silene Expert, renseigner au moins un filtre taxonomique (family/genus/species).",
        )
    try:
        start_date, end_date = parse_query_date_range(date_from, date_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="date_from/date_to must be YYYY-MM-DD and date_from <= date_to.")

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
    if not cached_export_matches(EXPORT_FILE, signature):
        search_silene_expert_mapped(
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

    return FileResponse(
        path=str(EXPORT_FILE),
        media_type="text/csv; charset=utf-8",
        filename="resultats_silene_expert.csv",
        headers={"Cache-Control": "no-store"},
    )
