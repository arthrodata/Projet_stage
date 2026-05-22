from fastapi import APIRouter

from Backend.app.services.silene_service import (
    get_main_stats,
    get_observations_maille,
    get_rank_stats,
    search_commune,
    search_taxon,
)

router = APIRouter(prefix="/silene", tags=["silene"])


@router.get("/main-stats")
def main_stats():
    return get_main_stats()


@router.get("/rank-stats")
def rank_stats():
    return get_rank_stats()


@router.get("/search-taxon")
def autocomplete_taxon(search: str, limit: int = 20):
    return search_taxon(search=search, limit=limit)


@router.get("/search-commune")
def autocomplete_commune(search: str, limit: int = 20):
    return search_commune(search=search, limit=limit)


@router.get("/observations-maille/{cd_ref}")
def observations_maille(cd_ref: int):
    return get_observations_maille(cd_ref)

