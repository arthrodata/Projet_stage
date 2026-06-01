from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

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
    limit: int = 100,
    page: int = 1,
):
    return search_silene_expert_mapped(
        family=family,
        genus=genus,
        species=species,
        country=country,
        limit=limit,
        page=page,
    )


@router.get("/search/csv")
def export_csv(
    family: str = None,
    genus: str = None,
    species: str = None,
    country: str = None,
    limit: int = 200,
    max_pages: int = 50,
):
    if not any([(family or "").strip(), (genus or "").strip(), (species or "").strip()]):
        raise HTTPException(
            status_code=400,
            detail="Pour exporter un CSV Silene Expert, renseigner au moins un filtre taxonomique (family/genus/species).",
        )
    search_silene_expert_mapped(
        family=family,
        genus=genus,
        species=species,
        country=country,
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
