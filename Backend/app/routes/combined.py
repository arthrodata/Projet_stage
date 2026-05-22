from fastapi import APIRouter

from Backend.app.services.combined_service import search_gbif_and_silene_expert

router = APIRouter(prefix="/combined", tags=["combined"])


@router.get("/search")
def search(
    family: str = None,
    genus: str = None,
    species: str = None,
    country: str = None,
    limit: int = 100,
    page: int = 1,
):
    return search_gbif_and_silene_expert(
        family=family,
        genus=genus,
        species=species,
        country=country,
        limit=limit,
        page=page,
        export_csv=True,
    )

