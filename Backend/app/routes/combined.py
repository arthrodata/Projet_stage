from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from Backend.app.services.combined_service import COMBINED_EXPORT_FILE, search_gbif_and_silene_expert

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
            detail="Pour exporter un CSV combine, renseigner au moins un filtre taxonomique (family/genus/species).",
        )
    search_gbif_and_silene_expert(
        family=family,
        genus=genus,
        species=species,
        country=country,
        limit=limit,
        page=1,
        fetch_all=True,
        include_iucn=False,
        max_pages=max_pages,
        export_csv=True,
        export_file=COMBINED_EXPORT_FILE,
    )

    return FileResponse(
        path=str(COMBINED_EXPORT_FILE),
        media_type="text/csv; charset=utf-8",
        filename="resultats_gbif_silene.csv",
        headers={"Cache-Control": "no-store"},
    )
