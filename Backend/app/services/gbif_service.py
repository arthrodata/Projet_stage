from pathlib import Path

import pandas as pd
import requests

from Backend.app.services.iucn_service import IUCN_EMPTY_STATUS, get_iucn_enrichment


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

    response = requests.get(GBIF_COUNTRIES_URL, timeout=20)
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
    response = requests.get(
        GBIF_SPECIES_MATCH_URL,
        params={"name": family, "rank": "FAMILY"},
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()
    if data.get("rank") != "FAMILY":
        return None

    return data.get("usageKey") or data.get("familyKey")


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
    export_csv: bool = True,
    export_file: Path | None = None,
):
    params = {"basisOfRecord": TARGET_BASIS_OF_RECORD, "limit": 100}
    q_parts = []
    country_code = None

    if family:
        family_key = get_gbif_family_key(family)
        if family_key:
            params["taxonKey"] = family_key
        else:
            params["q"] = family

    if genus:
        q_parts.append(genus)
    if species:
        q_parts.append(species)

    if country:
        country_code = get_country_code(country)
        if country_code:
            params["country"] = country_code

    if q_parts:
        params["q"] = " ".join(q_parts)

    response = requests.get(
        "https://api.gbif.org/v1/occurrence/search",
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    df = pd.DataFrame(response.json().get("results", []))
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

    df = _add_iucn_columns(df)
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
