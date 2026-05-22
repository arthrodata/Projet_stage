from fastapi import APIRouter

from Backend.app.services.silene_expert_service import (
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
