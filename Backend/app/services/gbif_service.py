import requests
import pandas as pd
from pathlib import Path

EXPORT_FILE = Path(__file__).resolve().parents[2] / "exports" / "resultats.csv"


def search_gbif(
    genus=None,
    species=None,
    country=None
):

    url = "https://api.gbif.org/v1/occurrence/search"

    params = {
        "family": "Tortricidae",
        "limit": 100
    }
    q_parts = []

    if genus:
        q_parts.append(genus)

    if species:
        q_parts.append(species)

    if country:
        params["country"] = country

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
            "locality",
            "eventDate",
            "basisOfRecord",
            "datasetName",
            "family",
            "genus",
            "species"
        ]).to_csv(EXPORT_FILE, index=False)
        return []

    df["genus"] = df["genus"].fillna("")
    df["species"] = df["species"].fillna("")
    df["scientificName"] = df["scientificName"].fillna("")
    df["country"] = df["country"].fillna("")

    if genus:
        df = df[df["genus"].str.contains(genus, case=False, na=False) |
                df["scientificName"].str.contains(genus, case=False, na=False)]

    if species:
        df = df[df["species"].str.contains(species, case=False, na=False) |
                df["scientificName"].str.contains(species, case=False, na=False)]

    if country:
        df = df[df["country"].str.contains(country, case=False, na=False)]

    columns = [
        "country",
        "locality",
        "eventDate",
        "basisOfRecord",
        "datasetName",
        "family",
        "genus",
        "species"
    ]
    df = df.reindex(columns=columns)
    df = df.fillna("Non renseigné")

    EXPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(EXPORT_FILE, index=False)

    return df.to_dict(orient="records")