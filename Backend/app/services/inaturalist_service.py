from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests

from Backend.app.services.iucn_service import IUCN_EMPTY_STATUS, get_iucn_enrichments
from Backend.app.utils.date_filters import filter_rows_by_date_range
from Backend.app.utils.row_normalization import CSV_EXPORT_COLUMNS, normalize_rows


INATURALIST_API_BASE_URL = "https://api.inaturalist.org/v1"
EXPORT_FILE = Path(__file__).resolve().parents[2] / "exports" / "resultats_inaturalist.csv"
DEFAULT_QUALITY_GRADE = "research,needs_id,casual"


def _session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    return s


@lru_cache(maxsize=256)
def _place_id_for_country(country: str) -> Optional[int]:
    query = (country or "").strip()
    if not query:
        return None

    try:
        response = _session().get(
            f"{INATURALIST_API_BASE_URL}/places/autocomplete",
            params={"q": query, "per_page": 5},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return None

    query_lower = query.casefold()
    for item in results:
        if not isinstance(item, dict):
            continue
        name = str(item.get("display_name") or item.get("name") or "").casefold()
        if name == query_lower or name.startswith(f"{query_lower},") or query_lower in name:
            place_id = item.get("id")
            return int(place_id) if isinstance(place_id, int) else None

    return None


@lru_cache(maxsize=2048)
def _taxon_details(taxon_id: int) -> dict[str, Any]:
    try:
        response = _session().get(f"{INATURALIST_API_BASE_URL}/taxa/{int(taxon_id)}", timeout=20)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return {}

    results = payload.get("results") if isinstance(payload, dict) else None
    first = results[0] if isinstance(results, list) and results else None
    return first if isinstance(first, dict) else {}


@lru_cache(maxsize=4096)
def _places_by_ids(place_ids: tuple[int, ...]) -> list[dict[str, Any]]:
    ids = tuple(dict.fromkeys(int(place_id) for place_id in place_ids if isinstance(place_id, int)))
    if not ids:
        return []

    try:
        response = _session().get(
            f"{INATURALIST_API_BASE_URL}/places/{','.join(str(place_id) for place_id in ids)}",
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    results = payload.get("results") if isinstance(payload, dict) else None
    return [item for item in results if isinstance(item, dict)] if isinstance(results, list) else []


def _country_from_observation(observation: dict[str, Any]) -> str:
    return _country_from_places(observation, None)


def _country_from_places(observation: dict[str, Any], places_by_id: dict[int, dict[str, Any]] | None) -> str:
    place_ids = observation.get("place_ids")
    if isinstance(place_ids, list):
        if places_by_id is None:
            places = _places_by_ids(tuple(place_id for place_id in place_ids if isinstance(place_id, int)))
        else:
            places = [
                places_by_id[place_id]
                for place_id in place_ids
                if isinstance(place_id, int) and place_id in places_by_id
            ]
        for place in places:
            if place.get("admin_level") == 0 or place.get("place_type") == 12:
                name = place.get("name")
                if name:
                    return str(name).strip()

    place_guess = str(observation.get("place_guess") or "").strip()
    if "," in place_guess:
        last_part = place_guess.rsplit(",", 1)[-1].strip()
        if last_part:
            return last_part
    return place_guess or "Non renseigne"


def _taxon_value_by_rank(taxon: dict[str, Any], rank: str) -> Optional[str]:
    if not isinstance(taxon, dict):
        return None

    if str(taxon.get("rank") or "").casefold() == rank.casefold():
        name = taxon.get("name")
        return str(name).strip() if name else None

    ancestors = taxon.get("ancestors")
    if isinstance(ancestors, list):
        for ancestor in ancestors:
            if not isinstance(ancestor, dict):
                continue
            if str(ancestor.get("rank") or "").casefold() == rank.casefold():
                name = ancestor.get("name")
                return str(name).strip() if name else None

    return None


def _taxon_from_observation(observation: dict[str, Any]) -> dict[str, Any]:
    taxon = observation.get("taxon")
    if not isinstance(taxon, dict):
        return {}

    taxon_id = taxon.get("id")
    if isinstance(taxon_id, int):
        details = _taxon_details(taxon_id)
        if details:
            merged = dict(taxon)
            merged.update(details)
            return merged

    return taxon


def _coordinates_from_observation(observation: dict[str, Any]) -> str:
    geojson = observation.get("geojson")
    coords = geojson.get("coordinates") if isinstance(geojson, dict) else None
    if isinstance(coords, list) and len(coords) >= 2:
        lon, lat = coords[0], coords[1]
        if lat not in (None, "") and lon not in (None, ""):
            return f"{lat}, {lon}"

    location = observation.get("location")
    if isinstance(location, str) and "," in location:
        return location

    return "Non renseigne"


def _event_date_from_observation(observation: dict[str, Any]) -> str:
    observed_on = observation.get("observed_on")
    if observed_on:
        return str(observed_on)

    details = observation.get("observed_on_details")
    if isinstance(details, dict) and details.get("date"):
        return str(details.get("date"))

    for key in ("time_observed_at", "created_at"):
        value = observation.get(key)
        if isinstance(value, str) and len(value) >= 10:
            return value[:10]

    return "Non renseigne"


def _split_species_name(name: str | None) -> tuple[str, str]:
    parts = str(name or "").strip().split()
    if len(parts) >= 2:
        return parts[0], " ".join(parts[:2])
    if len(parts) == 1:
        return parts[0], parts[0]
    return "Non renseigne", "Non renseigne"


def _map_observation(
    observation: dict[str, Any],
    *,
    family_filter: str | None = None,
    genus_filter: str | None = None,
    places_by_id: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    taxon = _taxon_from_observation(observation)
    taxon_name = str(taxon.get("name") or "").strip()
    genus_from_name, species_from_name = _split_species_name(taxon_name)

    family_value = _taxon_value_by_rank(taxon, "family") or family_filter or "Non renseigne"
    genus_value = _taxon_value_by_rank(taxon, "genus") or genus_filter or genus_from_name
    species_value = taxon_name if taxon_name else species_from_name

    return {
        "source_bdd": "iNaturalist",
        "country": _country_from_places(observation, places_by_id),
        "coordinates": _coordinates_from_observation(observation),
        "eventDate": _event_date_from_observation(observation),
        "basisOfRecord": "HUMAN_OBSERVATION",
        "datasetName": "iNaturalist",
        "family": family_value or "Non renseigne",
        "genus": genus_value or "Non renseigne",
        "species": species_value or "Non renseigne",
        "quality_grade": observation.get("quality_grade") or "Non renseigne",
    }


def _apply_taxon_filters(
    rows: list[dict[str, Any]],
    *,
    family: str | None,
    genus: str | None,
    species: str | None,
) -> list[dict[str, Any]]:
    filtered = rows
    if family and family.strip():
        fam = family.strip().casefold()
        filtered = [row for row in filtered if fam in str(row.get("family") or "").casefold()]
    if genus and genus.strip():
        gen = genus.strip().casefold()
        filtered = [row for row in filtered if gen in str(row.get("genus") or "").casefold()]
    if species and species.strip():
        sp = species.strip().casefold()
        filtered = [row for row in filtered if sp in str(row.get("species") or "").casefold()]
    return filtered


def _enrich_iucn(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enrichments = get_iucn_enrichments([str(row.get("species") or "") for row in rows])
    for row in rows:
        species_name = str(row.get("species") or "").strip()
        enrichment = enrichments.get(species_name, {})
        status = enrichment.get("iucn_status") or IUCN_EMPTY_STATUS
        row["iucn_status"] = status
        row["status"] = status
    return rows


def _export_rows(rows: list[dict[str, Any]], export_file: Path) -> None:
    export_file.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(normalize_rows(rows, columns=CSV_EXPORT_COLUMNS)).reindex(columns=CSV_EXPORT_COLUMNS).to_csv(
        export_file,
        index=False,
        encoding="utf-8-sig",
    )


def search_inaturalist(
    family: Optional[str] = None,
    genus: Optional[str] = None,
    species: Optional[str] = None,
    country: Optional[str] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    quality_grade: str | None = None,
    limit: int = 100,
    page: int = 1,
    *,
    export_csv: bool = True,
    export_file: Path | None = None,
    fetch_all: bool = False,
    include_iucn: bool = True,
    max_pages: int | None = None,
    max_records: int | None = None,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit) if limit else 100, 200))
    safe_page = int(page) if page and int(page) > 0 else 1

    taxon_name = (species or "").strip() or (genus or "").strip() or (family or "").strip()
    params: dict[str, Any] = {
        "per_page": safe_limit,
        "quality_grade": (quality_grade or DEFAULT_QUALITY_GRADE).strip(),
        "order_by": "observed_on",
        "order": "desc",
    }
    if taxon_name:
        params["taxon_name"] = taxon_name
    if date_from:
        params["d1"] = date_from.isoformat()
    if date_to:
        params["d2"] = date_to.isoformat()

    country_place_id = _place_id_for_country(country) if country and country.strip() else None
    if country_place_id:
        params["place_id"] = country_place_id

    def fetch_page(page_number: int) -> list[dict[str, Any]]:
        response = _session().get(
            f"{INATURALIST_API_BASE_URL}/observations",
            params={**params, "page": int(page_number)},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results") if isinstance(payload, dict) else None
        return [item for item in results if isinstance(item, dict)] if isinstance(results, list) else []

    observations: list[dict[str, Any]] = []
    if fetch_all:
        current_page = 1
        pages = 0
        while True:
            batch = fetch_page(current_page)
            if not batch:
                break
            observations.extend(batch)
            if max_records is not None and len(observations) >= int(max_records):
                observations = observations[: int(max_records)]
                break
            if len(batch) < safe_limit:
                break
            current_page += 1
            pages += 1
            if max_pages is not None and pages >= int(max_pages):
                break
    else:
        observations = fetch_page(safe_page)

    all_place_ids = tuple(
        place_id
        for observation in observations
        for place_id in (observation.get("place_ids") or [])
        if isinstance(place_id, int)
    )
    places_by_id = {int(place["id"]): place for place in _places_by_ids(all_place_ids) if isinstance(place.get("id"), int)}

    rows = [
        _map_observation(observation, family_filter=family, genus_filter=genus, places_by_id=places_by_id)
        for observation in observations
    ]

    rows = _apply_taxon_filters(rows, family=family, genus=genus, species=species)
    if country and country.strip() and not country_place_id:
        country_query = country.strip().casefold()
        rows = [row for row in rows if country_query in str(row.get("country") or "").casefold()]
    rows = filter_rows_by_date_range(rows, date_from=date_from, date_to=date_to)

    if include_iucn:
        rows = _enrich_iucn(rows)
    else:
        for row in rows:
            row["iucn_status"] = IUCN_EMPTY_STATUS
            row["status"] = IUCN_EMPTY_STATUS

    if export_csv:
        _export_rows(rows, export_file or EXPORT_FILE)

    return normalize_rows(rows)
