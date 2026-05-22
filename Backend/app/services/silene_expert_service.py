from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests

from Backend.app.services.iucn_service import get_iucn_status


# Service Silene Expert
# Authentification : Silene Expert renvoie un cookie "token=...".
# On ne met jamais ce token en dur dans le code : on le lit depuis une variable d'environnement.

SILENE_EXPERT_BASE_URL = "https://expert.silene.eu"
TAXHUB_API_BASE_URL = "https://taxhub.silene.eu/api"
EXPORT_FILE = Path(__file__).resolve().parents[2] / "exports" / "resultats_silene_expert.csv"


def _session() -> requests.Session:
    s = requests.Session()
    # Ignore les variables proxy (certaines configs cassent les appels HTTP)
    s.trust_env = False
    return s


def _get_token() -> Optional[str]:
    # 2 noms possibles, pour être souple
    return os.getenv("SILENE_EXPERT_TOKEN") or os.getenv("SILENE_TOKEN")


def _taxhub_lookup_cd_ref(name: str) -> Optional[int]:
    """
    Convertit un nom (famille/genre/espèce) en cd_ref via TaxHub.
    On l'utilise pour filtrer Silene Expert avec `cd_ref`.
    """
    query = (name or "").strip()
    if not query:
        return None

    try:
        s = requests.Session()
        s.trust_env = False
        r = s.get(
            f"{TAXHUB_API_BASE_URL}/taxref/allnamebylist",
            params={"search_name": query, "limit": 20},
            timeout=20,
        )
        r.raise_for_status()
        items = r.json()
        if not isinstance(items, list) or not items:
            return None

        query_lower = query.lower()

        # 1) match exact sur lb_nom
        for item in items:
            if not isinstance(item, dict):
                continue
            lb_nom = (item.get("lb_nom") or "").strip()
            if lb_nom and lb_nom.lower() == query_lower:
                cd_ref = item.get("cd_ref")
                return int(cd_ref) if cd_ref is not None else None

        # 2) match "commence par" sur nom_valide
        for item in items:
            if not isinstance(item, dict):
                continue
            nom_valide = (item.get("nom_valide") or "").strip()
            if nom_valide and nom_valide.lower().startswith(query_lower):
                cd_ref = item.get("cd_ref")
                return int(cd_ref) if cd_ref is not None else None

        # 3) fallback : premier résultat
        first = items[0]
        if isinstance(first, dict) and first.get("cd_ref") is not None:
            return int(first.get("cd_ref"))
    except (requests.RequestException, ValueError):
        return None

    return None


def _taxhub_get_taxon_info(cd_nom: int) -> dict[str, Any]:
    """
    Récupère les infos taxonomiques via TaxHub (ex: famille, ordre...).
    """
    try:
        s = requests.Session()
        s.trust_env = False
        r = s.get(f"{TAXHUB_API_BASE_URL}/taxref/{int(cd_nom)}", timeout=20)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            return data
    except (requests.RequestException, ValueError):
        return {}
    return {}


def _taxhub_get_cd_refs_by_family(family: str, max_items: int = 50) -> list[int]:
    """
    Récupère une liste de cd_ref (espèces) appartenant à une famille via TaxHub.
    Sert à faire un "vrai" filtre famille pour Silene Expert.
    """
    fam = (family or "").strip()
    if not fam:
        return []

    try:
        s = requests.Session()
        s.trust_env = False
        r = s.get(
            f"{TAXHUB_API_BASE_URL}/taxref",
            params={"famille": fam, "id_rang": "ES", "limit": int(max_items), "offset": 0},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []

        out: list[int] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            cd_ref = it.get("cd_ref")
            if isinstance(cd_ref, int):
                out.append(cd_ref)
            elif isinstance(cd_ref, str) and cd_ref.strip().isdigit():
                out.append(int(cd_ref.strip()))

        # uniq
        return list(dict.fromkeys(out))
    except (requests.RequestException, ValueError):
        return []


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    """
    La structure exacte peut varier, donc on teste plusieurs clés.
    On retourne une liste de dict (enregistrements).
    """
    if payload is None:
        return []

    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]

    if not isinstance(payload, dict):
        return []

    for key in ("results", "data", "items", "records", "features"):
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]

    # Parfois c'est déjà 1 enregistrement
    if any(isinstance(v, (str, int, float, dict, list)) for v in payload.values()):
        return [payload]

    return []


def _iter_points(coords: Any):
    """
    Parcours récursif des coordonnées GeoJSON pour récupérer une liste de points (lon, lat).
    """
    if coords is None:
        return

    if isinstance(coords, (list, tuple)) and len(coords) == 2 and all(
        isinstance(x, (int, float)) for x in coords
    ):
        yield float(coords[0]), float(coords[1])
        return

    if isinstance(coords, (list, tuple)):
        for item in coords:
            yield from _iter_points(item)


def _coordinates_from_geometry(geometry: dict[str, Any]) -> Optional[str]:
    """
    Convertit une géométrie GeoJSON en "lat, lon" (centroïde simple).
    """
    if not isinstance(geometry, dict):
        return None

    coords = geometry.get("coordinates")
    points = list(_iter_points(coords))
    if not points:
        return None

    lon_avg = sum(p[0] for p in points) / len(points)
    lat_avg = sum(p[1] for p in points) / len(points)
    return f"{lat_avg}, {lon_avg}"


def _pick_first(record: dict[str, Any], keys: list[str]) -> Any:
    for k in keys:
        if k in record and record.get(k) not in (None, ""):
            return record.get(k)
    return None


def search_silene_expert(
    payload: Optional[dict[str, Any]] = None,
    *,
    export_csv: bool = True,
    export_file: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Appelle l'endpoint Silene Expert utilisé par le front web :
    POST /api/synthese/for_web?with_areas=false

    - Si pas de token, retourne [] (et exporte un CSV vide)
    - Ne plante pas si l'API change un peu ou si une clé manque
    - Ajoute iucn_status (avec cache par espèce)
    """
    token = _get_token()
    effective_export_file = export_file or EXPORT_FILE

    # Si pas de token : on ne peut pas accéder aux données Expert
    if not token:
        if export_csv:
            effective_export_file.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                columns=[
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
                ]
            ).to_csv(effective_export_file, index=False, encoding="utf-8-sig")
        return []

    url = f"{SILENE_EXPERT_BASE_URL}/api/synthese/for_web"
    params = {"with_areas": "false"}

    # Silene Expert utilise un cookie "token=..."
    cookies = {"token": token}

    try:
        r = _session().post(url, params=params, json=payload or {}, cookies=cookies, timeout=30)
        if r.status_code in (401, 403):
            return []
        if r.status_code == 404:
            return []
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError):
        return []

    rows: list[dict[str, Any]] = []
    taxon_cache: dict[int, dict[str, Any]] = {}

    # 1) Cas "GeoJSON FeatureCollection" (observations groupées par géométrie)
    if isinstance(data, dict) and isinstance(data.get("features"), list):
        for feature in data.get("features", []):
            if not isinstance(feature, dict):
                continue
            geometry = feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {}
            coords = _coordinates_from_geometry(geometry)

            props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
            observations = props.get("observations")

            if isinstance(observations, list) and observations:
                for obs in observations:
                    if not isinstance(obs, dict):
                        continue

                    cd_nom = obs.get("cd_nom")
                    taxon_info: dict[str, Any] = {}
                    if isinstance(cd_nom, str) and cd_nom.strip().isdigit():
                        cd_nom = int(cd_nom.strip())
                    if isinstance(cd_nom, int):
                        if cd_nom not in taxon_cache:
                            taxon_cache[cd_nom] = _taxhub_get_taxon_info(cd_nom)
                        taxon_info = taxon_cache.get(cd_nom, {})

                    scientific_name = _pick_first(
                        obs,
                        [
                            "nom_valide",
                            "scientific_name",
                            "scientificName",
                            "lb_nom",
                            "taxon_name",
                            "nom_vern_or_lb_nom",
                        ],
                    )
                    dataset = _pick_first(obs, ["jdd_nom", "dataset_name", "datasetName", "dataset"])
                    event_date = _pick_first(obs, ["date_debut", "date_min", "eventDate", "date"])

                    species_value = (str(scientific_name).strip() if scientific_name else "Non renseigné")
                    genus_value = "Non renseigné"
                    if species_value and species_value != "Non renseigné":
                        genus_value = species_value.split(" ", 1)[0]

                    family_value = _pick_first(obs, ["famille", "family"])
                    if not family_value and isinstance(taxon_info, dict):
                        family_value = taxon_info.get("famille")

                    rows.append(
                        {
                            "country": "France",
                            "coordinates": coords or "Non renseigné",
                            "eventDate": event_date or "Non renseigné",
                            "basisOfRecord": _pick_first(obs, ["type_source", "url_source"]) or "Non renseigné",
                            "datasetName": dataset or "Silene Expert",
                            "family": family_value or "Non renseigné",
                            "genus": genus_value,
                            "species": species_value,
                        }
                    )

    # 2) Autres cas (liste/dict)
    if not rows:
        records = _extract_records(data)
        if not records:
            return []

        for rec in records:
            scientific_name = _pick_first(
                rec,
                ["scientific_name", "scientificName", "nom_scientifique", "nom_valide", "taxon_name", "lb_nom"],
            )
            genus = _pick_first(rec, ["genus", "genre"])
            species = _pick_first(rec, ["species", "espece"]) or scientific_name

            lat = _pick_first(rec, ["latitude", "lat", "y", "decimallatitude", "decimalLatitude", "y_centroid_4326"])
            lon = _pick_first(rec, ["longitude", "lon", "lng", "x", "decimallongitude", "decimalLongitude", "x_centroid_4326"])

            coordinates = None
            if lat not in (None, "") and lon not in (None, ""):
                coordinates = f"{lat}, {lon}"

            event_date = _pick_first(rec, ["eventDate", "date", "date_obs", "date_observation", "date_min", "date_debut"])

            rows.append(
                {
                    "country": _pick_first(rec, ["country", "pays"]) or "Non renseigné",
                    "coordinates": coordinates or "Non renseigné",
                    "eventDate": event_date or "Non renseigné",
                    "basisOfRecord": _pick_first(rec, ["basisOfRecord", "type_observation", "source", "type_source"]) or "Non renseigné",
                    "datasetName": _pick_first(rec, ["datasetName", "dataset", "jeu_de_donnees", "jdd_nom", "dataset_name"]) or "Silene Expert",
                    "family": _pick_first(rec, ["family", "famille"]) or "Non renseigné",
                    "genus": genus or "Non renseigné",
                    "species": (str(species).strip() if species else "Non renseigné"),
                }
            )

    df = pd.DataFrame(rows)

    # Identifier la base de données source
    df["source_bdd"] = "Silene Expert"

    # Cache IUCN : une espèce unique = 1 appel IUCN
    species_clean = df["species"].fillna("").astype(str).map(lambda s: s.strip())
    unique_species = species_clean.unique().tolist()

    status_dict: dict[str, str] = {}
    for sp in unique_species:
        if not sp or sp == "Non renseigné":
            status_dict[sp] = "Non renseigné"
        else:
            status_dict[sp] = get_iucn_status(sp)

    df["iucn_status"] = species_clean.map(status_dict).fillna("NE")
    # Colonne standardisée (exports) pour l'IUCN Red List
    df["status"] = df["iucn_status"]

    df = df.fillna("Non renseigné")

    # Mettre source_bdd en première colonne dans le CSV
    ordered_cols = ["source_bdd"] + [c for c in df.columns if c != "source_bdd"]
    df = df.reindex(columns=ordered_cols)

    if export_csv:
        effective_export_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(effective_export_file, index=False, encoding="utf-8-sig")

    return df.to_dict(orient="records")


def _export_mapped_rows(rows: list[dict[str, Any]], export_file: Path) -> None:
    """
    Export CSV pour les résultats "mappés" (mêmes champs que GBIF).
    On évite de réécrire toute la logique de `search_silene_expert` quand on
    a besoin de désactiver l'export pendant des appels intermédiaires.
    """
    export_file.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    if df.empty:
        pd.DataFrame(
            columns=[
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
            ]
        ).to_csv(export_file, index=False, encoding="utf-8-sig")
        return

    # Mettre source_bdd en première colonne
    if "source_bdd" in df.columns:
        ordered_cols = ["source_bdd"] + [c for c in df.columns if c != "source_bdd"]
        df = df.reindex(columns=ordered_cols)

    if "status" not in df.columns:
        if "iucn_status" in df.columns:
            df["status"] = df["iucn_status"]
        else:
            df["status"] = ""

    df.to_csv(export_file, index=False, encoding="utf-8-sig")


def search_silene_expert_mapped(
    family: Optional[str] = None,
    genus: Optional[str] = None,
    species: Optional[str] = None,
    country: Optional[str] = None,
    limit: int = 100,
    page: int = 1,
    *,
    export_csv: bool = True,
    export_file: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Version "simple" pour le front : mêmes champs que la recherche GBIF.

    Mapping actuel (simple, lisible) :
    - on filtre Silene Expert avec les clés texte `family`, `genus`, `species`
    - `country` n'est pas utilisé pour l'instant (Silene Expert est centré France)
    """
    payload: dict[str, Any] = {"page": int(page), "limit": int(limit)}

    # Silene Expert accepte certains filtres texte (vérifié) :
    # - species/nom_valide : OK
    # - family : non fiable côté API, on filtre côté backend après enrichment TaxHub
    # Pour genus, le plus fiable est d'utiliser cd_ref (TaxHub) pour le genre.
    if family and family.strip():
        # On ne met pas "family" dans le payload (ça ne filtre pas réellement sur l'API),
        # on filtrera ensuite sur la colonne "family".
        family = family.strip()

    if species and species.strip():
        payload["species"] = species.strip()

    if genus and genus.strip():
        cd_ref = _taxhub_lookup_cd_ref(genus.strip())
        if cd_ref is not None:
            payload["cd_ref"] = cd_ref
        else:
            payload["genus"] = genus.strip()

    # Fallback cd_ref (si jamais l'API change et ignore les filtres texte)
    if not any(payload.get(k) for k in ("family", "genus", "species", "cd_ref")):
        name_for_taxhub = (species or "").strip() or (genus or "").strip() or (family or "").strip()
        cd_ref = _taxhub_lookup_cd_ref(name_for_taxhub) if name_for_taxhub else None
        if cd_ref is not None:
            payload["cd_ref"] = cd_ref

    # Si l'utilisateur met un pays différent de France, on retourne vide (cohérence minimale).
    if country and country.strip() and country.strip().lower() not in {"fr", "france"}:
        return []

    def apply_family_filter(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not family or not family.strip():
            return items
        fam = family.strip().lower()
        return [r for r in items if fam in ((r.get("family") or "").strip().lower())]

    # Filtre famille : on récupère des cd_ref d'espèces de cette famille via TaxHub,
    # puis on interroge Silene Expert avec cd_ref jusqu'à obtenir assez de résultats.
    if family and family.strip() and not (genus and genus.strip()) and not (species and species.strip()):
        cd_refs = _taxhub_get_cd_refs_by_family(family.strip(), max_items=50)
        collected: list[dict[str, Any]] = []
        for cd_ref in cd_refs[:15]:
            batch = search_silene_expert(
                payload={"cd_ref": cd_ref, "limit": int(limit), "page": 1},
                export_csv=False,
            )
            batch = apply_family_filter(batch)
            collected.extend(batch)
            if len(collected) >= int(limit):
                break
        collected = collected[: int(limit)]
        if export_csv:
            _export_mapped_rows(collected, export_file=export_file or EXPORT_FILE)
        return collected

    rows = search_silene_expert(payload=payload, export_csv=False)
    rows = apply_family_filter(rows)
    if export_csv:
        _export_mapped_rows(rows, export_file=export_file or EXPORT_FILE)
    return rows
