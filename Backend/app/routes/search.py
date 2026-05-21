from fastapi import APIRouter
from Backend.app.services.gbif_service import search_gbif


router = APIRouter()

@router.get("/search")
def search(
    family: str = None,
    genus: str = None,
    species: str = None,
    country: str = None
):

    data = search_gbif(
        family,
        genus,
        species,
        country
    )

    return data
