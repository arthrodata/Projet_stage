from pathlib import Path

from concurrent.futures import ThreadPoolExecutor
from datetime import date
import logging
import threading
import time
import pandas as pd
import requests
from requests.adapters import HTTPAdapter

from Backend.app.services.iucn_service import IUCN_EMPTY_STATUS, get_iucn_enrichments
from Backend.app.utils.date_filters import parse_any_date
from Backend.app.utils.row_normalization import (
    CSV_EXPORT_COLUMNS,
    STANDARD_COLUMNS,
    normalize_dataframe,
)


EXPORT_FILE = Path(__file__).resolve().parents[2] / "exports" / "gbif_results.csv"
TARGET_BASIS_OF_RECORD = "HUMAN_OBSERVATION"
GBIF_SPECIES_MATCH_URL = "https://api.gbif.org/v1/species/match"
GBIF_COUNTRIES_URL = "https://api.gbif.org/v1/enumeration/country"
EXPORT_COLUMNS = STANDARD_COLUMNS
GBIF_OCCURRENCE_SEARCH_URL = "https://api.gbif.org/v1/occurrence/search"
GBIF_MAX_PAGE_LIMIT = 300
TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
TRANSIENT_REQUEST_EXCEPTIONS = (requests.Timeout, requests.ConnectionError)
_THREAD_LOCAL = threading.local()
logger = logging.getLogger(__name__)


def _session() -> requests.Session:
    session = getattr(_THREAD_LOCAL, "gbif_session", None)
    session_factory = getattr(_THREAD_LOCAL, "gbif_session_factory", None)
    if session is None or session_factory is not requests.Session:
        session = requests.Session()
        session.trust_env = False
        if hasattr(session, "mount"):
            adapter = HTTPAdapter(pool_connections=16, pool_maxsize=16)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
        _THREAD_LOCAL.gbif_session = session
        _THREAD_LOCAL.gbif_session_factory = requests.Session
    return session


def get_country_code(country):
    if not country:
        return None

    country = country.strip()
    if len(country) == 2:
        return country.upper()

    country_lower = country.casefold()
    aliases = {
        "algerie": "DZ",
        "algerie": "DZ",
        "usa": "US",
        "u.s.a": "US",
        "etats-unis": "US",
        "royaume-uni": "GB",
        "uk": "GB",
    }
    if country_lower in aliases:
        return aliases[country_lower]

    response = _session().get(GBIF_COUNTRIES_URL, timeout=20)
    response.raise_for_status()
    for item in response.json():
        names = [
            item.get("title"),
            item.get("iso2"),
            item.get("iso3"),
            item.get("enumName", "").replace("_", " "),
        ]
        if any(name and name.casefold() == country_lower for name in names):
            return item.get("iso2")

    return None


def get_gbif_family_key(family):
    response = _session().get(
        GBIF_SPECIES_MATCH_URL,
        params={"name": family, "rank": "FAMILY"},
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()
    if data.get("rank") != "FAMILY":
        return None

    return data.get("usageKey") or data.get("familyKey")


def get_gbif_taxon_key(name: str, rank: str) -> int | None:
    query = (name or "").strip()
    if not query:
        return None

    response = _session().get(
        GBIF_SPECIES_MATCH_URL,
        params={"name": query, "rank": rank},
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()
    if str(data.get("rank") or "").upper() != str(rank).upper():
        return None

    key = data.get("usageKey") or data.get("speciesKey") or data.get("genusKey") or data.get("familyKey")
    return int(key) if isinstance(key, int) else None


def _apply_most_specific_taxon_filter(
    params: dict,
    q_parts: list[str],
    *,
    family: str | None = None,
    genus: str | None = None,
    species: str | None = None,
) -> str | None:
    """
    GBIF accepts a single taxonKey. Use the most specific user filter so
    pagination is spent on the requested taxon, not on a broader parent group.
    """
    if species and str(species).strip():
        species_value = str(species).strip()
        species_key = get_gbif_taxon_key(species_value, "SPECIES")
        if species_key:
            params["taxonKey"] = species_key
        else:
            q_parts.append(species_value)
        return "species"

    if genus and str(genus).strip():
        genus_value = str(genus).strip()
        genus_key = get_gbif_taxon_key(genus_value, "GENUS")
        if genus_key:
            params["taxonKey"] = genus_key
        else:
            q_parts.append(genus_value)
        return "genus"

    if family and str(family).strip():
        family_value = str(family).strip()
        family_key = get_gbif_family_key(family_value)
        if family_key:
            params["taxonKey"] = family_key
        else:
            q_parts.append(family_value)
        return "family"

    return None


def _format_coordinates(row):
    latitude = row.get("decimalLatitude")
    longitude = row.get("decimalLongitude")
    if pd.isna(latitude) or pd.isna(longitude):
        return None

    return f"{latitude}, {longitude}"


def _add_iucn_columns(df):
    enrichments = get_iucn_enrichments(df["species"].fillna("").astype(str).unique().tolist())

    def value(species, key):
        return enrichments.get(str(species), {}).get(key)

    for column in (
        "iucn_status",
        "iucn_lookup_status",
        "iucn_assessment_id",
        "iucn_year",
        "iucn_scope",
    ):
        df[column] = df["species"].map(lambda species, key=column: value(species, key))

    df["iucn_status"] = df["iucn_status"].fillna(IUCN_EMPTY_STATUS)
    df["status"] = df["iucn_status"]
    df["redListCategory"] = df["iucn_status"]
    return df


def _empty_export(export_file):
    export_file.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns=CSV_EXPORT_COLUMNS).to_csv(
        export_file,
        index=False,
        encoding="utf-8-sig",
    )


def search_gbif(
    family=None,
    genus=None,
    species=None,
    country=None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
    page: int = 1,
    export_csv: bool = True,
    export_file: Path | None = None,
    *,
    fetch_all: bool = False,
    include_iucn: bool = True,
    max_pages: int | None = None,
    max_records: int | None = None,
):
    requested_limit = int(limit) if limit and int(limit) > 0 else 100
    safe_limit = min(requested_limit, GBIF_MAX_PAGE_LIMIT)
    safe_page = int(page) if page and int(page) > 0 else 1

    params = {
        "basisOfRecord": TARGET_BASIS_OF_RECORD,
        "limit": safe_limit,
        "orderBy": "eventDate",
        "order": "desc",
    }
    q_parts = []
    country_code = None

    # GBIF supporte les intervalles via `eventDate=YYYY-MM-DD,YYYY-MM-DD`.
    # Pour 1 seule borne (date_from OU date_to), on laisse l'API sans filtre
    # et on filtre ensuite cote backend (formats eventDate variables).
    if date_from and date_to:
        params["eventDate"] = f"{date_from.isoformat()},{date_to.isoformat()}"

    selected_taxon_rank = _apply_most_specific_taxon_filter(params, q_parts, family=family, genus=genus, species=species)

    if country:
        country_code = get_country_code(country)
        if country_code:
            params["country"] = country_code

    if q_parts:
        params["q"] = " ".join(q_parts)

    def fetch_page(offset: int) -> dict:
        last_error: requests.RequestException | None = None
        for attempt in range(3):
            request_params = {**params, "offset": int(offset)}
            logger.info(
                "external_request source=GBIF url=%s params=%s attempt=%s",
                GBIF_OCCURRENCE_SEARCH_URL,
                request_params,
                attempt + 1,
            )
            try:
                r = _session().get(
                    GBIF_OCCURRENCE_SEARCH_URL,
                    params=request_params,
                    timeout=30,
                )
                if getattr(r, "status_code", None) in TRANSIENT_STATUS_CODES and attempt < 2:
                    logger.warning(
                        "external_retry source=GBIF status=%s offset=%s attempt=%s",
                        getattr(r, "status_code", None),
                        offset,
                        attempt + 1,
                    )
                    time.sleep(0.5 * (attempt + 1))
                    continue
                r.raise_for_status()
                data = r.json()
                results = data.get("results") if isinstance(data, dict) else []
                logger.info(
                    "external_response source=GBIF offset=%s rows=%s endOfRecords=%s count=%s",
                    offset,
                    len(results) if isinstance(results, list) else 0,
                    data.get("endOfRecords") if isinstance(data, dict) else None,
                    data.get("count") if isinstance(data, dict) else None,
                )
                return data if isinstance(data, dict) else {}
            except requests.RequestException as exc:
                last_error = exc
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                is_transient_exception = isinstance(exc, TRANSIENT_REQUEST_EXCEPTIONS)
                if (
                    not is_transient_exception
                    and status_code not in TRANSIENT_STATUS_CODES
                ) or attempt >= 2:
                    logger.warning("external_error source=GBIF offset=%s error=%s", offset, exc)
                    raise
                time.sleep(0.5 * (attempt + 1))
        if last_error:
            raise last_error
        return {}

    if fetch_all:
        first_data = fetch_page(offset=0)
        first_results = first_data.get("results") if isinstance(first_data.get("results"), list) else []
        all_results: list[dict] = list(first_results)

        page_cap = int(max_pages) if max_pages is not None else None
        if max_records is not None:
            record_pages = (int(max_records) + safe_limit - 1) // safe_limit
            page_cap = min(page_cap, record_pages) if page_cap is not None else record_pages

        if first_results and first_data.get("endOfRecords") is not True and (page_cap is None or page_cap > 1):
            if isinstance(first_data.get("count"), int):
                count_pages = (int(first_data["count"]) + safe_limit - 1) // safe_limit
                page_cap = min(page_cap, count_pages) if page_cap is not None else count_pages

            if page_cap is not None:
                offsets = [page_number * safe_limit for page_number in range(1, max(1, page_cap))]
                workers = min(8, len(offsets)) if offsets else 0
                if workers:
                    with ThreadPoolExecutor(max_workers=workers) as executor:
                        page_payloads = list(executor.map(fetch_page, offsets))
                    for data in page_payloads:
                        results = data.get("results") if isinstance(data.get("results"), list) else []
                        if results:
                            all_results.extend(results)
                        if data.get("endOfRecords") is True:
                            break
            else:
                offset = safe_limit
                while True:
                    data = fetch_page(offset=offset)
                    results = data.get("results") if isinstance(data.get("results"), list) else []
                    if not results:
                        break
                    all_results.extend(results)
                    if data.get("endOfRecords") is True:
                        break
                    if max_records is not None and len(all_results) >= int(max_records):
                        break
                    offset += safe_limit

        if max_records is not None and len(all_results) >= int(max_records):
            all_results = all_results[: int(max_records)]
        logger.info(
            "pagination_summary source=GBIF fetch_all=true page_limit=%s max_pages=%s max_records=%s rows=%s",
            safe_limit,
            max_pages,
            max_records,
            len(all_results),
        )
        df = pd.DataFrame(all_results)
    else:
        offset = (safe_page - 1) * safe_limit
        data = fetch_page(offset=offset)
        df = pd.DataFrame(data.get("results", []))
    effective_export_file = export_file or EXPORT_FILE

    if df.empty:
        if export_csv:
            _empty_export(effective_export_file)
        return []

    for column in ("genus", "species", "scientificName", "country", "family", "basisOfRecord"):
        if column not in df.columns:
            df[column] = ""
        df[column] = df[column].fillna("")

    df = df[df["basisOfRecord"] == TARGET_BASIS_OF_RECORD]
    df["coordinates"] = df.apply(_format_coordinates, axis=1)

    if genus:
        df = df[
            df["genus"].str.contains(genus, case=False, na=False)
            | df["scientificName"].str.contains(genus, case=False, na=False)
        ]
    if species:
        df = df[
            df["species"].str.contains(species, case=False, na=False)
            | df["scientificName"].str.contains(species, case=False, na=False)
        ]
    if country and not country_code:
        df = df[df["country"].str.contains(country, case=False, na=False)]
    if family and selected_taxon_rank not in {"genus", "species"}:
        df = df[df["family"].str.contains(family, case=False, na=False)]

    # Filtre date (avant enrichment IUCN pour limiter les appels)
    if (date_from or date_to) and "eventDate" in df.columns:
        parsed = df["eventDate"].map(parse_any_date)
        mask = parsed.notna()
        if date_from:
            mask &= parsed >= date_from
        if date_to:
            mask &= parsed <= date_to
        df = df[mask]

    if include_iucn:
        df = _add_iucn_columns(df)
    else:
        df["iucn_status"] = IUCN_EMPTY_STATUS
        df["status"] = IUCN_EMPTY_STATUS
        df["redListCategory"] = IUCN_EMPTY_STATUS
    df["source_bdd"] = "GBIF"
    df = normalize_dataframe(df, columns=EXPORT_COLUMNS, sort_by_event_date=True)

    if export_csv:
        effective_export_file.parent.mkdir(parents=True, exist_ok=True)
        df.reindex(columns=CSV_EXPORT_COLUMNS).to_csv(
            effective_export_file,
            index=False,
            encoding="utf-8-sig",
        )

    return df.to_dict(orient="records")


def estimate_gbif_count(
    family: str | None = None,
    genus: str | None = None,
    species: str | None = None,
    country: str | None = None,
) -> int:
    """
    Retourne le nombre total d'occurrences GBIF correspondant aux filtres.
    Utilise `limit=0` pour obtenir rapidement le champ `count`.
    """
    params = {"basisOfRecord": TARGET_BASIS_OF_RECORD, "limit": 0, "offset": 0}
    q_parts: list[str] = []

    _apply_most_specific_taxon_filter(params, q_parts, family=family, genus=genus, species=species)

    if country:
        country_code = get_country_code(country)
        if country_code:
            params["country"] = country_code
        else:
            # Pas de code -> on ne peut pas estimer correctement via l'API GBIF,
            # on garde une estimation conservative.
            return 0

    if q_parts:
        params["q"] = " ".join(q_parts)

    response = _session().get("https://api.gbif.org/v1/occurrence/search", params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        return 0
    count = data.get("count")
    return int(count) if isinstance(count, int) else 0
