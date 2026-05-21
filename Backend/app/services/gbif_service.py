import pandas as pd
import requests
import os
from pathlib import Path

EXPORT_FILE = Path(__file__).resolve().parents[2] / "exports" / "resultats.csv"
TARGET_BASIS_OF_RECORD = "HUMAN_OBSERVATION"
IUCN_FAMILY_URL = "https://api.iucnredlist.org/api/v4/taxa/family/{family}"
GBIF_SPECIES_MATCH_URL = "https://api.gbif.org/v1/species/match"
GBIF_COUNTRIES_URL = "https://api.gbif.org/v1/enumeration/country"


def get_country_code(country):
    if not country:
        return None

    country = country.strip()
    if len(country) == 2:
        return country.upper()

    country_lower = country.lower()
    aliases = {
        "algerie": "DZ",
        "algérie": "DZ",
        "usa": "US",
        "u.s.a": "US",
        "etats-unis": "US",
        "états-unis": "US",
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

        if any(name and name.lower() == country_lower for name in names):
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


def get_iucn_statuses_by_species(family):
    token = os.environ.get("IUCN_TOKEN")
    if not token:
        return {}

    response = requests.get(
        IUCN_FAMILY_URL.format(family=family),
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    response.raise_for_status()

    assessments = response.json().get("assessments", [])
    statuses = {}

    for assessment in assessments:
        if not assessment.get("latest"):
            continue

        scientific_name = assessment.get("taxon_scientific_name")
        category = assessment.get("red_list_category_code")

        if scientific_name and category:
            statuses[scientific_name.lower()] = category

    return statuses


def search_gbif(
    family=None,
    genus=None,
    species=None,
    country=None
):

    url = "https://api.gbif.org/v1/occurrence/search"

    params = {
        "basisOfRecord": TARGET_BASIS_OF_RECORD,
        "limit": 100
    }
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

    response = requests.get(url, params=params)
    response.raise_for_status()

    data = response.json()
    results = data.get("results", [])

    df = pd.DataFrame(results)

    if df.empty:
        EXPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=[
            "country",
            "coordinates",
            "eventDate",
            "basisOfRecord",
            "datasetName",
            "family",
            "genus",
            "species",
            "redListCategory"
        ]).to_csv(EXPORT_FILE, index=False, encoding="utf-8-sig")
        return []

    df["genus"] = df["genus"].fillna("")
    df["species"] = df["species"].fillna("")
    df["scientificName"] = df["scientificName"].fillna("")
    df["country"] = df["country"].fillna("")
    df["family"] = df["family"].fillna("")
    df["basisOfRecord"] = df["basisOfRecord"].fillna("")
    df = df[df["basisOfRecord"] == TARGET_BASIS_OF_RECORD]

    def format_coordinates(row):
        latitude = row.get("decimalLatitude")
        longitude = row.get("decimalLongitude")

        if pd.isna(latitude) or pd.isna(longitude):
            return None

        return f"{latitude}, {longitude}"

    df["coordinates"] = df.apply(format_coordinates, axis=1)

    if genus:
        df = df[df["genus"].str.contains(genus, case=False, na=False) |
                df["scientificName"].str.contains(genus, case=False, na=False)]

    if species:
        df = df[df["species"].str.contains(species, case=False, na=False) |
                df["scientificName"].str.contains(species, case=False, na=False)]

    if country and not country_code:
        df = df[df["country"].str.contains(country, case=False, na=False)]

    if family:
        df = df[df["family"].str.contains(family, case=False, na=False)]

    iucn_statuses = {}
    should_lookup_iucn = bool(family or genus or species)

    if should_lookup_iucn:
        for family_name in df["family"].dropna().unique():
            if not family_name:
                continue

            try:
                iucn_statuses.update(get_iucn_statuses_by_species(family_name))
            except requests.RequestException:
                continue

    def find_iucn_status(row):
        names = [
            row.get("species"),
            row.get("scientificName"),
        ]

        for name in names:
            if name and str(name).lower() in iucn_statuses:
                return iucn_statuses[str(name).lower()]

        return None

    df["redListCategory"] = df.apply(find_iucn_status, axis=1)

    columns = [
        "country",
        "coordinates",
        "eventDate",
        "basisOfRecord",
        "datasetName",
        "family",
        "genus",
        "species",
        "redListCategory"
    ]
    df = df.reindex(columns=columns)
    df = df.fillna("Non renseigné")

    EXPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(EXPORT_FILE, index=False, encoding="utf-8-sig")

    return df.to_dict(orient="records")
