from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from Backend.app.services.inaturalist_service import EXPORT_FILE, search_inaturalist
from Backend.app.utils.date_filters import parse_query_date_range


router = APIRouter(prefix="/inaturalist", tags=["inaturalist"])


@router.get("/search")
def search(
    family: str = None,
    genus: str = None,
    species: str = None,
    country: str = None,
    date_from: str = None,
    date_to: str = None,
    quality_grade: str = None,
    limit: int = 100,
    page: int = 1,
):
    try:
        start_date, end_date = parse_query_date_range(date_from, date_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="date_from/date_to must be YYYY-MM-DD and date_from <= date_to.")

    return search_inaturalist(
        family=family,
        genus=genus,
        species=species,
        country=country,
        date_from=start_date,
        date_to=end_date,
        quality_grade=quality_grade,
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
    quality_grade: str = None,
    limit: int = 200,
    max_pages: int = 50,
):
    if not any([(family or "").strip(), (genus or "").strip(), (species or "").strip()]):
        raise HTTPException(
            status_code=400,
            detail="Pour exporter un CSV iNaturalist, renseigner au moins un filtre taxonomique (family/genus/species).",
        )
    try:
        start_date, end_date = parse_query_date_range(date_from, date_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="date_from/date_to must be YYYY-MM-DD and date_from <= date_to.")

    search_inaturalist(
        family=family,
        genus=genus,
        species=species,
        country=country,
        date_from=start_date,
        date_to=end_date,
        quality_grade=quality_grade,
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
        filename="resultats_inaturalist.csv",
        headers={"Cache-Control": "no-store"},
    )
