from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from Backend.app.utils.date_filters import parse_query_date_range

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
    return search_silene_expert_mapped(
        family=family,
        genus=genus,
        species=species,
        country=country,
        date_from=start_date,
        date_to=end_date,
        limit=limit,
        page=page,
    )


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

    return FileResponse(
        path=str(EXPORT_FILE),
        media_type="text/csv; charset=utf-8",
        filename="resultats_silene_expert.csv",
        headers={"Cache-Control": "no-store"},
    )
