from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests

from Backend.app.services.iucn_service import IUCN_EMPTY_STATUS, get_iucn_enrichments
from Backend.app.utils.date_filters import filter_rows_by_date_range
from Backend.app.utils.row_normalization import CSV_EXPORT_COLUMNS, normalize_dataframe, normalize_rows


# Service Silene Expert
# Authentification : Silene Expert renvoie un cookie "token=...".
# On ne met jamais ce token en dur dans le code : on le lit depuis une variable d'environnement.

SILENE_EXPERT_BASE_URL = "https://expert.silene.eu"
TAXHUB_API_BASE_URL = "https://taxhub.silene.eu/api"
EXPORT_FILE = Path(__file__).resolve().parents[2] / "exports" / "resultats_silene_expert.csv"
DEFAULT_SILENE_EXPERT_APP_ID = "3"


def _env_flag(name: str, default: bool = False) -> bool:
    value = (os.getenv(name) or "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _normalize_silene_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    prepared: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item.setdefault("source_bdd", "Silene Expert")
        prepared.append(item)
    return normalize_rows(prepared, sort_by_event_date=True)


def _session() -> requests.Session:
    s = requests.Session()
    # En local on ignore les proxys par defaut, mais certains serveurs
    # universitaires exigent HTTP(S)_PROXY / REQUESTS_CA_BUNDLE.
    s.trust_env = _env_flag("SILENE_TRUST_ENV", default=False)
    return s


def _b64url_decode(segment: str) -> bytes:
    import base64

    seg = (segment or "").strip()
    if not seg:
        return b""
    pad = "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(seg + pad)


def _jwt_claims_no_verify(token: str) -> dict[str, Any]:
    """
    Decode un JWT sans verifier la signature (uniquement pour lire exp/iat).
    Silene Expert fournit un token au format JWT (header.payload.signature).
    """
    tok = (token or "").strip()
    parts = tok.split(".")
    if len(parts) < 2:
        return {}

    import json

    claims: dict[str, Any] = {}
    for segment in (parts[0], parts[1]):
        try:
            raw = _b64url_decode(segment)
            obj = json.loads(raw.decode("utf-8"))
            if isinstance(obj, dict):
                claims.update(obj)
        except Exception:
            continue
    return claims


@dataclass
class _SileneTokenCache:
    token: str | None = None
    exp_epoch: int | None = None


_TOKEN_CACHE = _SileneTokenCache()
_TOKEN_LOCK = threading.Lock()


def _token_is_valid(token: str, *, min_ttl_seconds: int = 120) -> bool:
    claims = _jwt_claims_no_verify(token)
    exp = claims.get("exp")
    try:
        exp_int = int(exp) if exp is not None else None
    except (TypeError, ValueError):
        exp_int = None

    if exp_int is None:
        return True

    return (exp_int - int(time.time())) > int(min_ttl_seconds)


def _login_and_get_token() -> Optional[str]:
    """
    Auth Silene Expert :
    POST https://expert.silene.eu/api/auth/login
    payload: {login, password, id_application}
    -> renvoie un cookie `token=...`
    """
    login = (os.getenv("SILENE_EXPERT_LOGIN") or "").strip()
    password = (os.getenv("SILENE_EXPERT_PASSWORD") or "").strip()
    if not login or not password:
        return None

    try:
        app_id = int((os.getenv("SILENE_EXPERT_APP_ID") or DEFAULT_SILENE_EXPERT_APP_ID).strip())
    except ValueError:
        app_id = 3

    url = f"{SILENE_EXPERT_BASE_URL}/api/auth/login"
    payload = {"login": login, "password": password, "id_application": app_id}

    try:
        r = _session().post(url, json=payload, timeout=30)
        # 490 = erreur custom (pas d'utilisateur / mauvais mdp, etc.)
        if r.status_code >= 400:
            return None

        token = r.cookies.get("token")
        if token and isinstance(token, str) and token.strip():
            return token.strip()
    except requests.RequestException:
        return None

    return None


def _get_token() -> Optional[str]:
    """
    Retourne un token valide si possible.

    Ordre :
    - cache memoire (si encore valide)
    - env SILENE_EXPERT_TOKEN/SILENE_TOKEN (si encore valide)
    - si identifiants fournis : login auto et mise a jour du cache + os.environ
    """
    with _TOKEN_LOCK:
        if _TOKEN_CACHE.token and _token_is_valid(_TOKEN_CACHE.token):
            return _TOKEN_CACHE.token

    env_token = (os.getenv("SILENE_EXPERT_TOKEN") or os.getenv("SILENE_TOKEN") or "").strip()
    if env_token and _token_is_valid(env_token):
        with _TOKEN_LOCK:
            _TOKEN_CACHE.token = env_token
        return env_token

    fresh = _login_and_get_token()
    if not fresh:
        return env_token or None

    with _TOKEN_LOCK:
        _TOKEN_CACHE.token = fresh
        claims = _jwt_claims_no_verify(fresh)
        exp = claims.get("exp")
        try:
            _TOKEN_CACHE.exp_epoch = int(exp) if exp is not None else None
        except (TypeError, ValueError):
            _TOKEN_CACHE.exp_epoch = None

    os.environ["SILENE_EXPERT_TOKEN"] = fresh
    return fresh


def _force_refresh_token() -> Optional[str]:
    fresh = _login_and_get_token()
    if not fresh:
        return None
    with _TOKEN_LOCK:
        _TOKEN_CACHE.token = fresh
        claims = _jwt_claims_no_verify(fresh)
        exp = claims.get("exp")
        try:
            _TOKEN_CACHE.exp_epoch = int(exp) if exp is not None else None
        except (TypeError, ValueError):
            _TOKEN_CACHE.exp_epoch = None
    os.environ["SILENE_EXPERT_TOKEN"] = fresh
    return fresh


def diagnose_silene_expert() -> dict[str, Any]:
    token = _get_token()
    return {
        "base_url": SILENE_EXPERT_BASE_URL,
        "taxhub_url": TAXHUB_API_BASE_URL,
        "login_configured": bool((os.getenv("SILENE_EXPERT_LOGIN") or "").strip()),
        "password_configured": bool((os.getenv("SILENE_EXPERT_PASSWORD") or "").strip()),
        "manual_token_configured": bool((os.getenv("SILENE_EXPERT_TOKEN") or os.getenv("SILENE_TOKEN") or "").strip()),
        "token_available": bool(token),
        "token_valid": bool(token and _token_is_valid(token)),
        "trust_env": _session().trust_env,
        "https_proxy_configured": bool((os.getenv("HTTPS_PROXY") or os.getenv("https_proxy") or "").strip()),
        "requests_ca_bundle_configured": bool((os.getenv("REQUESTS_CA_BUNDLE") or "").strip()),
    }


def _taxhub_lookup_cd_ref(name: str) -> Optional[int]:
    """
    Convertit un nom (famille/genre/espece) en cd_ref via TaxHub.
    On l'utilise pour filtrer Silene Expert avec `cd_ref`.
    """
    query = (name or "").strip()
    if not query:
        return None

    try:
        s = _session()
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

        # 3) fallback : premier resultat
        first = items[0]
        if isinstance(first, dict) and first.get("cd_ref") is not None:
            return int(first.get("cd_ref"))
    except (requests.RequestException, ValueError):
        return None

    return None


def _taxhub_get_taxon_info(cd_nom: int) -> dict[str, Any]:
    """
    Recupere les infos taxonomiques via TaxHub (ex: famille, ordre...).
    """
    try:
        s = _session()
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
    Recupere une liste de cd_ref (especes) appartenant a une famille via TaxHub.
    Sert a faire un "vrai" filtre famille pour Silene Expert.
    """
    fam = _normalize_family_query(family)
    if not fam:
        return []

    try:
        s = _session()
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


def _normalize_family_query(family: str | None) -> str:
    fam = (family or "").strip()
    if not fam:
        return ""
    return fam[:1].upper() + fam[1:].lower()


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    """
    La structure exacte peut varier, donc on teste plusieurs cles.
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

    # Parfois c'est deja  1 enregistrement
    if any(isinstance(v, (str, int, float, dict, list)) for v in payload.values()):
        return [payload]

    return []


def _iter_points(coords: Any):
    """
    Parcours recursif des coordonnees GeoJSON pour recuperer une liste de points (lon, lat).
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
    Convertit une geometrie GeoJSON en "lat, lon" (centroide simple).
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
    include_iucn: bool = True,
) -> list[dict[str, Any]]:
    """
    Appelle l'endpoint Silene Expert utilise par le front web :
    POST /api/synthese/for_web?with_areas=false

    - Si pas de token, retourne [] (et exporte un CSV vide)
    - Ne plante pas si l'API change un peu ou si une cle manque
    - Ajoute iucn_status (avec cache par espece)
    """
    token = _get_token()
    effective_export_file = export_file or EXPORT_FILE

    # Si pas de token : on ne peut pas acceder aux donnees Expert
    if not token:
        if export_csv:
            effective_export_file.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                columns=CSV_EXPORT_COLUMNS
            ).to_csv(effective_export_file, index=False, encoding="utf-8-sig")
        return []

    url = f"{SILENE_EXPERT_BASE_URL}/api/synthese/for_web"
    params = {"with_areas": "false"}

    def do_request(tok: str) -> requests.Response:
        # Silene Expert utilise un cookie "token=..."
        return _session().post(
            url,
            params=params,
            json=payload or {},
            cookies={"token": tok},
            timeout=30,
        )

    try:
        r = do_request(token)
        if r.status_code in (401, 403):
            refreshed = _force_refresh_token()
            if refreshed:
                r = do_request(refreshed)
        if r.status_code in (401, 403, 404):
            return []
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError):
        return []

    rows: list[dict[str, Any]] = []
    taxon_cache: dict[int, dict[str, Any]] = {}

    # 1) Cas "GeoJSON FeatureCollection" (observations groupees par geometrie)
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

                    species_value = (str(scientific_name).strip() if scientific_name else "Non renseigne")
                    genus_value = "Non renseigne"
                    if species_value and species_value != "Non renseigne":
                        genus_value = species_value.split(" ", 1)[0]

                    family_value = _pick_first(obs, ["famille", "family"])
                    if not family_value and isinstance(taxon_info, dict):
                        family_value = taxon_info.get("famille")

                    rows.append(
                        {
                            "country": "France",
                            "coordinates": coords or "Non renseigne",
                            "eventDate": event_date or "Non renseigne",
                            "basisOfRecord": _pick_first(obs, ["type_source", "url_source"]) or "Non renseigne",
                            "datasetName": dataset or "Silene Expert",
                            "family": family_value or "Non renseigne",
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
                    "country": _pick_first(rec, ["country", "pays"]) or "Non renseigne",
                    "coordinates": coordinates or "Non renseigne",
                    "eventDate": event_date or "Non renseigne",
                    "basisOfRecord": _pick_first(rec, ["basisOfRecord", "type_observation", "source", "type_source"]) or "Non renseigne",
                    "datasetName": _pick_first(rec, ["datasetName", "dataset", "jeu_de_donnees", "jdd_nom", "dataset_name"]) or "Silene Expert",
                    "family": _pick_first(rec, ["family", "famille"]) or "Non renseigne",
                    "genus": genus or "Non renseigne",
                    "species": (str(species).strip() if species else "Non renseigne"),
                }
            )

    df = pd.DataFrame(rows)

    # Identifier la base de donnees source
    df["source_bdd"] = "Silene Expert"

    if include_iucn:
        # Cache IUCN : une espece unique = 1 appel IUCN
        species_clean = df["species"].fillna("").astype(str).map(lambda s: s.strip())
        unique_species = species_clean.unique().tolist()

        enrichments = get_iucn_enrichments(
            [
                species
                for species in unique_species
                if species and species not in {"Non renseigne", "Non renseigne"}
            ]
        )

        def iucn_value(species_name, key):
            return enrichments.get(species_name, {}).get(key)

        for column in (
            "iucn_status",
            "iucn_lookup_status",
            "iucn_assessment_id",
            "iucn_year",
            "iucn_scope",
        ):
            df[column] = species_clean.map(lambda name, key=column: iucn_value(name, key))

        df["iucn_status"] = df["iucn_status"].fillna(IUCN_EMPTY_STATUS)
        # Colonne standardisee (exports) pour l'IUCN Red List
        df["status"] = df["iucn_status"]
    else:
        df["iucn_status"] = IUCN_EMPTY_STATUS
        df["iucn_lookup_status"] = "skipped"
        df["iucn_assessment_id"] = ""
        df["iucn_year"] = ""
        df["iucn_scope"] = ""
        df["status"] = IUCN_EMPTY_STATUS

    df = normalize_dataframe(df)

    # Mettre source_bdd en premiere colonne dans le CSV
    ordered_cols = ["source_bdd"] + [c for c in df.columns if c != "source_bdd"]
    df = df.reindex(columns=ordered_cols)

    if export_csv:
        effective_export_file.parent.mkdir(parents=True, exist_ok=True)
        df.reindex(columns=CSV_EXPORT_COLUMNS).to_csv(
            effective_export_file,
            index=False,
            encoding="utf-8-sig",
        )

    return df.to_dict(orient="records")


def _export_mapped_rows(rows: list[dict[str, Any]], export_file: Path) -> None:
    """
    Export CSV pour les resultats "mappes" (memes champs que GBIF).
    On evite de reecrire toute la logique de `search_silene_expert` quand on
    a besoin de desactiver l'export pendant des appels intermediaires.
    """
    export_file.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(_normalize_silene_rows(rows))
    if df.empty:
        pd.DataFrame(
            columns=CSV_EXPORT_COLUMNS
        ).to_csv(export_file, index=False, encoding="utf-8-sig")
        return

    # Mettre source_bdd en premiere colonne
    if "source_bdd" in df.columns:
        ordered_cols = ["source_bdd"] + [c for c in df.columns if c != "source_bdd"]
        df = df.reindex(columns=ordered_cols)

    if "status" not in df.columns:
        if "iucn_status" in df.columns:
            df["status"] = df["iucn_status"]
        else:
            df["status"] = ""

    df.reindex(columns=CSV_EXPORT_COLUMNS).to_csv(export_file, index=False, encoding="utf-8-sig")


def _enrich_mapped_rows_iucn(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return rows

    species_names = [
        str(row.get("species") or "").strip()
        for row in rows
        if str(row.get("species") or "").strip()
        and str(row.get("species") or "").strip() != "Non renseigne"
    ]
    enrichments = get_iucn_enrichments(species_names)

    for row in rows:
        species_name = str(row.get("species") or "").strip()
        enrichment = enrichments.get(species_name, {})
        status = enrichment.get("iucn_status") or IUCN_EMPTY_STATUS
        row["iucn_status"] = status
        row["iucn_lookup_status"] = enrichment.get("iucn_lookup_status") or ""
        row["iucn_assessment_id"] = enrichment.get("iucn_assessment_id") or ""
        row["iucn_year"] = enrichment.get("iucn_year") or ""
        row["iucn_scope"] = enrichment.get("iucn_scope") or ""
        row["status"] = status

    return rows


def search_silene_expert_mapped(
    family: Optional[str] = None,
    genus: Optional[str] = None,
    species: Optional[str] = None,
    country: Optional[str] = None,
    date_from: date | None = None,
    date_to: date | None = None,
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
    """
    Version "simple" pour le front : memes champs que la recherche GBIF.

    Mapping actuel (simple, lisible) :
    - on filtre Silene Expert avec les cles texte `family`, `genus`, `species`
    - `country` n'est pas utilise pour l'instant (Silene Expert est centre France)
    """
    safe_limit = int(limit) if limit and int(limit) > 0 else 100
    safe_page = int(page) if page and int(page) > 0 else 1

    if fetch_all:
        collected: list[dict[str, Any]] = []

        family_only = bool(family and family.strip()) and not (genus and genus.strip()) and not (species and species.strip())
        if family_only:
            cd_refs = _taxhub_get_cd_refs_by_family(family.strip(), max_items=50)
            for cd_ref in cd_refs:
                batch = search_silene_expert(
                    payload={"cd_ref": cd_ref, "limit": safe_limit, "page": 1},
                    export_csv=False,
                    include_iucn=False,
                )
                batch = [
                    r
                    for r in batch
                    if (family.strip().lower() in ((r.get("family") or "").strip().lower()))
                ]
                collected.extend(batch)

            collected = filter_rows_by_date_range(collected, date_from=date_from, date_to=date_to)
            if include_iucn:
                collected = _enrich_mapped_rows_iucn(collected)
            if export_csv:
                _export_mapped_rows(collected, export_file=export_file or EXPORT_FILE)
            return _normalize_silene_rows(collected)

        current_page = 1
        pages = 0
        while True:
            batch = search_silene_expert_mapped(
                family=family,
                genus=genus,
                species=species,
                country=country,
                date_from=date_from,
                date_to=date_to,
                limit=safe_limit,
                page=current_page,
                export_csv=False,
                fetch_all=False,
                include_iucn=False,
            )
            if not batch:
                break
            collected.extend(batch)
            if max_records is not None and len(collected) >= int(max_records):
                collected = collected[: int(max_records)]
                break
            if len(batch) < safe_limit:
                break
            current_page += 1
            pages += 1
            if max_pages is not None and pages >= int(max_pages):
                break

        collected = filter_rows_by_date_range(collected, date_from=date_from, date_to=date_to)
        if include_iucn:
            collected = _enrich_mapped_rows_iucn(collected)
        if export_csv:
            _export_mapped_rows(collected, export_file=export_file or EXPORT_FILE)
        return _normalize_silene_rows(collected)

    payload: dict[str, Any] = {"page": safe_page, "limit": safe_limit}

    # Silene Expert accepte certains filtres texte (verifie) :
    # - species/nom_valide : OK
    # - family : non fiable cote API, on filtre cote backend apres enrichment TaxHub
    # Pour genus, le plus fiable est d'utiliser cd_ref (TaxHub) pour le genre.
    if family and family.strip():
        # On ne met pas "family" dans le payload (ca ne filtre pas reellement sur l'API),
        # on filtrera ensuite sur la colonne "family".
        family = _normalize_family_query(family)

    if species and species.strip():
        cd_ref = _taxhub_lookup_cd_ref(species.strip())
        if cd_ref is not None:
            payload["cd_ref"] = cd_ref
        else:
            payload["species"] = species.strip()
    elif genus and genus.strip():
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

    # Si l'utilisateur met un pays different de France, on retourne vide (coherence minimale).
    if country and country.strip() and country.strip().lower() not in {"fr", "france"}:
        if export_csv:
            _export_mapped_rows([], export_file=export_file or EXPORT_FILE)
        return []

    def apply_family_filter(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not family or not family.strip():
            return items
        fam = family.strip().lower()
        return [r for r in items if fam in ((r.get("family") or "").strip().lower())]

    def apply_taxon_filters(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        filtered = apply_family_filter(items)
        if species and species.strip():
            expected_species = species.strip().lower()
            return [
                row
                for row in filtered
                if expected_species in ((row.get("species") or "").strip().lower())
            ]

        if genus and genus.strip():
            expected_genus = genus.strip().lower()
            return [
                row
                for row in filtered
                if expected_genus in ((row.get("genus") or "").strip().lower())
            ]

        return filtered

    # Filtre famille : on recupere des cd_ref d'especes de cette famille via TaxHub,
    # puis on interroge Silene Expert avec cd_ref jusqu'a obtenir assez de resultats.
    if family and family.strip() and not (genus and genus.strip()) and not (species and species.strip()):
        cd_refs = _taxhub_get_cd_refs_by_family(family.strip(), max_items=50)
        collected: list[dict[str, Any]] = []
        for cd_ref in cd_refs[:15]:
            batch = search_silene_expert(
                payload={"cd_ref": cd_ref, "limit": safe_limit, "page": 1},
                export_csv=False,
                include_iucn=False,
            )
            batch = apply_taxon_filters(batch)
            collected.extend(batch)
            if len(collected) >= safe_limit:
                break
        collected = collected[:safe_limit]
        collected = filter_rows_by_date_range(collected, date_from=date_from, date_to=date_to)
        if include_iucn:
            collected = _enrich_mapped_rows_iucn(collected)
        if export_csv:
            _export_mapped_rows(collected, export_file=export_file or EXPORT_FILE)
        return _normalize_silene_rows(collected)

    if include_iucn:
        rows = search_silene_expert(payload=payload, export_csv=False)
    else:
        rows = search_silene_expert(payload=payload, export_csv=False, include_iucn=False)
    rows = apply_taxon_filters(rows)
    rows = filter_rows_by_date_range(rows, date_from=date_from, date_to=date_to)
    if export_csv:
        _export_mapped_rows(rows, export_file=export_file or EXPORT_FILE)
    return _normalize_silene_rows(rows)
