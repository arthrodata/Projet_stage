from __future__ import annotations

from datetime import date
import logging
import os
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests

from Backend.app.services.gbif_service import get_country_code
from Backend.app.utils.date_filters import filter_rows_by_date_range
from Backend.app.utils.row_normalization import CSV_EXPORT_COLUMNS, normalize_rows


STELI_DATASET_ID = "4A9DDA1F-B8FD-3E13-E053-2614A8C02B7C"
STELI_GBIF_DATASET_KEY = "c709bf36-4964-4771-90f0-c6ba4b351620"
STELI_GBIF_OCCURRENCE_URL = "https://api.gbif.org/v1/occurrence/search"
STELI_DATASET_NAME = "Suivi Temporel des Libellules"
STELI_OPENOBS_PORTAL_URL = (
    "https://openobs.mnhn.fr/openobs-hub/occurrences/search"
    "?q=%28raw_occurrenceStatus%3A%22Pr%C3%A9sent%22%29+AND+"
    f"%28collectionCode%3A{STELI_DATASET_ID}%29#tab_mapView"
)
EXPORT_FILE = Path(__file__).resolve().parents[2] / "exports" / "resultats_steli.csv"

logger = logging.getLogger(__name__)


def _session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session


def _pick(item: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def _coordinates(item: dict[str, Any]) -> str:
    lat = _pick(item, ["decimalLatitude", "latitude", "lat", "y"])
    lon = _pick(item, ["decimalLongitude", "longitude", "lon", "lng", "x"])
    if lat not in (None, "") and lon not in (None, ""):
        return f"{lat}, {lon}"

    geojson = item.get("geojson")
    coords = geojson.get("coordinates") if isinstance(geojson, dict) else None
    if isinstance(coords, list) and len(coords) >= 2:
        return f"{coords[1]}, {coords[0]}"

    geometry = item.get("geometry")
    coords = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if isinstance(coords, list) and len(coords) >= 2:
        return f"{coords[1]}, {coords[0]}"

    return "Non renseigne"


def _species(item: dict[str, Any]) -> str:
    return str(_pick(item, ["species", "specificEpithet", "scientificName", "taxonName", "nomScientifique"]) or "")


def _genus(item: dict[str, Any], species_value: str) -> str:
    value = _pick(item, ["genus", "genre"])
    if value:
        return str(value)
    first = species_value.split(" ", 1)[0].strip()
    return first if first else ""


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("results", "records", "data", "occurrences", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    response = payload.get("response")
    docs = response.get("docs") if isinstance(response, dict) else None
    if isinstance(docs, list):
        return [item for item in docs if isinstance(item, dict)]

    return []


def _map_record(item: dict[str, Any]) -> dict[str, Any]:
    species_value = _species(item)
    return {
        "source_bdd": "STELI",
        "country": _pick(item, ["country", "countryCode", "pays"]) or "France",
        "coordinates": _coordinates(item),
        "eventDate": _pick(item, ["eventDate", "date", "dateObs", "observed_on", "observationDate"]),
        "basisOfRecord": _pick(item, ["basisOfRecord", "recordType"]) or "Human observation / Suivi protocole",
        "datasetName": _pick(item, ["datasetName", "collectionName"]) or STELI_DATASET_NAME,
        "family": _pick(item, ["family", "famille"]) or "",
        "genus": _genus(item, species_value),
        "species": species_value,
        "status": _pick(item, ["status", "iucn_status", "redListCategory"]) or "Non renseigne",
    }


def _matches_text(value: Any, expected: str | None) -> bool:
    needle = str(expected or "").strip().casefold()
    if not needle:
        return True
    return needle in str(value or "").casefold()


def _apply_filters(
    rows: list[dict[str, Any]],
    *,
    family: str | None,
    genus: str | None,
    species: str | None,
    country: str | None,
    start_date: date | None,
    end_date: date | None,
) -> list[dict[str, Any]]:
    filtered = [
        row
        for row in rows
        if _matches_text(row.get("family"), family)
        and _matches_text(row.get("genus"), genus)
        and _matches_text(row.get("species"), species)
        and _matches_text(row.get("country"), country)
    ]
    return filter_rows_by_date_range(filtered, date_from=start_date, date_to=end_date)


def _query_params(
    *,
    family: str | None,
    genus: str | None,
    species: str | None,
    country: str | None,
    start_date: date | None,
    end_date: date | None,
    limit: int,
    page: int,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "collectionCode": STELI_DATASET_ID,
        "dataset_id": STELI_DATASET_ID,
        "limit": int(limit),
        "page": int(page),
    }
    if family:
        params["family"] = family
    if genus:
        params["genus"] = genus
    if species:
        params["species"] = species
    if country:
        params["country"] = country
    if start_date:
        params["start_date"] = start_date.isoformat()
        params["date_from"] = start_date.isoformat()
    if end_date:
        params["end_date"] = end_date.isoformat()
        params["date_to"] = end_date.isoformat()
    return params


def _write_export(rows: list[dict[str, Any]], export_file: Path) -> None:
    export_file.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(normalize_rows(rows, columns=CSV_EXPORT_COLUMNS)).reindex(columns=CSV_EXPORT_COLUMNS).to_csv(
        export_file,
        index=False,
        encoding="utf-8-sig",
    )


def _gbif_steli_params(
    *,
    family: str | None,
    genus: str | None,
    species: str | None,
    country: str | None,
    start_date: date | None,
    end_date: date | None,
    limit: int,
    page: int,
) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit) if limit else 100, 300))
    safe_page = max(1, int(page) if page else 1)
    params: dict[str, Any] = {
        "datasetKey": STELI_GBIF_DATASET_KEY,
        "limit": safe_limit,
        "offset": (safe_page - 1) * safe_limit,
    }

    if species and species.strip():
        params["scientificName"] = species.strip()
    elif genus and genus.strip():
        params["q"] = genus.strip()
    elif family and family.strip():
        params["q"] = family.strip()

    if country and country.strip():
        code = get_country_code(country)
        if code:
            params["country"] = code

    if start_date and end_date:
        params["eventDate"] = f"{start_date.isoformat()},{end_date.isoformat()}"

    return params


def _map_gbif_record(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_bdd": "STELI",
        "country": item.get("country") or item.get("countryCode") or "France",
        "coordinates": _coordinates(item),
        "eventDate": item.get("eventDate") or item.get("dateIdentified"),
        "basisOfRecord": item.get("basisOfRecord") or "Human observation / Suivi protocole",
        "datasetName": STELI_DATASET_NAME,
        "family": item.get("family") or "",
        "genus": item.get("genus") or "",
        "species": item.get("species") or item.get("scientificName") or "",
        "status": "Non renseigne",
    }


def _search_steli_via_gbif(
    *,
    species: str | None,
    genus: str | None,
    family: str | None,
    country: str | None,
    start_date: date | None,
    end_date: date | None,
    limit: int,
    page: int,
    fetch_all: bool = False,
    max_pages: int | None = None,
    max_records: int | None = None,
) -> list[dict[str, str]]:
    logger.info("Calling STELI GBIF fallback with datasetKey %s", STELI_GBIF_DATASET_KEY)

    def fetch_page(page_number: int) -> tuple[list[dict[str, Any]], bool]:
        params = _gbif_steli_params(
            family=family,
            genus=genus,
            species=species,
            country=country,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            page=page_number,
        )
        try:
            response = _session().get(STELI_GBIF_OCCURRENCE_URL, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("STELI GBIF fallback unavailable: %s", exc)
            return [], True

        records = payload.get("results") if isinstance(payload, dict) else []
        end_of_records = bool(payload.get("endOfRecords")) if isinstance(payload, dict) else True
        return [record for record in records if isinstance(record, dict)], end_of_records

    if fetch_all:
        records: list[dict[str, Any]] = []
        current_page = 1
        pages = 0
        while True:
            batch, end_of_records = fetch_page(current_page)
            if not batch:
                break
            records.extend(batch)
            pages += 1
            if end_of_records:
                break
            if max_pages is not None and pages >= int(max_pages):
                break
            if max_records is not None and len(records) >= int(max_records):
                records = records[: int(max_records)]
                break
            current_page += 1
    else:
        records, _ = fetch_page(page)

    rows = [_map_gbif_record(record) for record in records if isinstance(record, dict)]
    rows = _apply_filters(
        rows,
        family=family,
        genus=genus,
        species=species,
        country=country,
        start_date=start_date,
        end_date=end_date,
    )
    return normalize_rows(rows)


def search_steli(
    species: Optional[str] = None,
    genus: Optional[str] = None,
    family: Optional[str] = None,
    country: Optional[str] = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 100,
    page: int = 1,
    *,
    export_csv: bool = True,
    export_file: Path | None = None,
    fetch_all: bool = False,
    max_pages: int | None = None,
    max_records: int | None = None,
) -> list[dict[str, str]]:
    """
    Recherche STELI.

    Vigie-Nature publie l'identifiant OpenObs du jeu STELI, mais pas un endpoint
    JSON stable documente. Si `STELI_API_URL` est defini, on l'interroge et on
    mappe les occurrences renvoyees. Sinon on retourne [] proprement.
    """
    effective_export_file = export_file or EXPORT_FILE
    api_url = (os.getenv("STELI_API_URL") or "").strip()

    if not api_url:
        logger.info(
            "STELI OpenObs JSON endpoint not configured; using GBIF dataset fallback. OpenObs portal: %s",
            STELI_OPENOBS_PORTAL_URL,
        )
        normalized = _search_steli_via_gbif(
            species=species,
            genus=genus,
            family=family,
            country=country,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            page=page,
            fetch_all=fetch_all,
            max_pages=max_pages,
            max_records=max_records,
        )
        if export_csv:
            _write_export(normalized, effective_export_file)
        return normalized

    safe_limit = max(1, int(limit) if limit else 100)
    safe_page = max(1, int(page) if page else 1)
    params = _query_params(
        family=family,
        genus=genus,
        species=species,
        country=country,
        start_date=start_date,
        end_date=end_date,
        limit=safe_limit,
        page=safe_page,
    )

    logger.info("Calling STELI endpoint %s with dataset %s", api_url, STELI_DATASET_ID)
    try:
        response = _session().get(api_url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("STELI endpoint unavailable or invalid: %s", exc)
        if export_csv:
            _write_export([], effective_export_file)
        return []

    rows = [_map_record(record) for record in _extract_records(payload)]
    rows = _apply_filters(
        rows,
        family=family,
        genus=genus,
        species=species,
        country=country,
        start_date=start_date,
        end_date=end_date,
    )
    normalized = normalize_rows(rows)

    if export_csv:
        _write_export(normalized, effective_export_file)

    return normalized
