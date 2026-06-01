from pathlib import Path

from datetime import date
import pandas as pd
import requests

from Backend.app.services.iucn_service import IUCN_EMPTY_STATUS, get_iucn_enrichment
from Backend.app.utils.date_filters import parse_any_date


EXPORT_FILE = Path(__file__).resolve().parents[2] / "exports" / "resultats.csv"
TARGET_BASIS_OF_RECORD = "HUMAN_OBSERVATION"
GBIF_SPECIES_MATCH_URL = "https://api.gbif.org/v1/species/match"
GBIF_COUNTRIES_URL = "https://api.gbif.org/v1/enumeration/country"
EXPORT_COLUMNS = [
    "source_bdd",
    "country",
    "coordinates",
    "eventDate",
    "basisOfRecord",
    "datasetName",
    "family",
    "genus",
    "species",
    "status",
    "iucn_status",
    "iucn_lookup_status",
    "iucn_assessment_id",
    "iucn_year",
    "iucn_scope",
    "redListCategory",
]
CSV_EXPORT_COLUMNS = [
    "source_bdd",
    "country",
    "coordinates",
    "eventDate",
    "basisOfRecord",
    "datasetName",
    "family",
    "genus",
    "species",
    "status",
]


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

    session = requests.Session()
    session.trust_env = False
    response = session.get(GBIF_COUNTRIES_URL, timeout=20)
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
    session = requests.Session()
    session.trust_env = False
    response = session.get(
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

    session = requests.Session()
    session.trust_env = False
    response = session.get(
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


def _format_coordinates(row):
    latitude = row.get("decimalLatitude")
    longitude = row.get("decimalLongitude")
    if pd.isna(latitude) or pd.isna(longitude):
        return None

    return f"{latitude}, {longitude}"


def _add_iucn_columns(df):
    enrichments = {
        species: get_iucn_enrichment(species)
        for species in df["species"].fillna("").astype(str).unique()
    }

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
    safe_limit = int(limit) if limit and int(limit) > 0 else 100
    safe_page = int(page) if page and int(page) > 0 else 1

    params = {"basisOfRecord": TARGET_BASIS_OF_RECORD, "limit": safe_limit}
    q_parts = []
    country_code = None

    # GBIF supporte les intervalles via `eventDate=YYYY-MM-DD,YYYY-MM-DD`.
    # Pour 1 seule borne (date_from OU date_to), on laisse l'API sans filtre
    # et on filtre ensuite cote backend (formats eventDate variables).
    if date_from and date_to:
        params["eventDate"] = f"{date_from.isoformat()},{date_to.isoformat()}"

    if family:
        family_key = get_gbif_family_key(family)
        if family_key:
            params["taxonKey"] = family_key
        else:
            params["q"] = family

    # Prefer GBIF taxonKey when possible (much faster than broad q= searches)
    if species:
        species_key = get_gbif_taxon_key(species, "SPECIES")
        if species_key:
            params["taxonKey"] = species_key
        else:
            q_parts.append(species)

    if genus and "taxonKey" not in params:
        genus_key = get_gbif_taxon_key(genus, "GENUS")
        if genus_key:
            params["taxonKey"] = genus_key
        else:
            q_parts.append(genus)

    if country:
        country_code = get_country_code(country)
        if country_code:
            params["country"] = country_code

    if q_parts:
        params["q"] = " ".join(q_parts)

    def fetch_page(offset: int) -> dict:
        session = requests.Session()
        session.trust_env = False
        r = session.get(
            "https://api.gbif.org/v1/occurrence/search",
            params={**params, "offset": int(offset)},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else {}

    if fetch_all:
        offset = 0
        pages = 0
        all_results: list[dict] = []
        while True:
            data = fetch_page(offset=offset)
            results = data.get("results") if isinstance(data.get("results"), list) else []
            if not results:
                break
            all_results.extend(results)
            if data.get("endOfRecords") is True:
                break
            pages += 1
            if max_pages is not None and pages >= int(max_pages):
                break
            if max_records is not None and len(all_results) >= int(max_records):
                all_results = all_results[: int(max_records)]
                break
            offset += safe_limit
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
    if family:
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
    df = df.reindex(columns=EXPORT_COLUMNS).fillna("Non renseigne")

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

    if family:
        family_key = get_gbif_family_key(family)
        if family_key:
            params["taxonKey"] = family_key
        else:
            params["q"] = family

    if species:
        species_key = get_gbif_taxon_key(species, "SPECIES")
        if species_key:
            params["taxonKey"] = species_key
        else:
            q_parts.append(species)

    if genus and "taxonKey" not in params:
        genus_key = get_gbif_taxon_key(genus, "GENUS")
        if genus_key:
            params["taxonKey"] = genus_key
        else:
            q_parts.append(genus)

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

    session = requests.Session()
    session.trust_env = False
    response = session.get("https://api.gbif.org/v1/occurrence/search", params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        return 0
    count = data.get("count")
    return int(count) if isinstance(count, int) else 0
