from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from Backend.app.services.gbif_service import EXPORT_FILE, search_gbif


router = APIRouter()

@router.get("/search")
def search(
    family: str = None,
    genus: str = None,
    species: str = None,
    country: str = None
):

    data = search_gbif(
        family=family,
        genus=genus,
        species=species,
        country=country,
        export_csv=True,
    )

    return data


@router.get("/search/csv")
def export_csv(
    family: str = None,
    genus: str = None,
    species: str = None,
    country: str = None,
    limit: int = 300,
    max_pages: int = 50,
):
    if not any([(family or "").strip(), (genus or "").strip(), (species or "").strip()]):
        raise HTTPException(
            status_code=400,
            detail="Pour exporter un CSV GBIF, renseigner au moins un filtre taxonomique (family/genus/species).",
        )
    search_gbif(
        family=family,
        genus=genus,
        species=species,
        country=country,
        limit=limit,
        fetch_all=True,
        include_iucn=True,
        max_pages=max_pages,
        export_csv=True,
        export_file=EXPORT_FILE,
    )

    return FileResponse(
        path=str(EXPORT_FILE),
        media_type="text/csv; charset=utf-8",
        filename="resultats_gbif.csv",
        headers={"Cache-Control": "no-store"},
    )
