from __future__ import annotations

from typing import Any, Optional

import requests


# Service Silene Nature (GeoNature-atlas)
# On appelle l'API publique de https://nature.silene.eu/ pour recuperer des donnees de synthese.

SILENE_BASE_URL = "https://nature.silene.eu"


def _session() -> requests.Session:
    s = requests.Session()
    # Ignore les variables proxy (certaines configs cassent les appels HTTP)
    s.trust_env = False
    return s


def get_main_stats() -> dict[str, Any]:
    """Statistiques globales (observations, taxons, communes, photos)."""
    try:
        r = _session().get(f"{SILENE_BASE_URL}/api/main_stat", timeout=15)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else {"data": data}
    except requests.RequestException:
        return {"error": "Erreur Silene"}
    except ValueError:
        return {"error": "Erreur Silene"}


def get_rank_stats() -> list[dict[str, Any]]:
    """Statistiques par grands groupes (format variable selon l'instance)."""
    try:
        r = _session().get(f"{SILENE_BASE_URL}/api/rank_stat", timeout=15)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except requests.RequestException:
        return []
    except ValueError:
        return []


def search_taxon(search: str, limit: int = 20) -> list[dict[str, Any]]:
    """Autocomplete taxons (label + value=cd_ref)."""
    search = (search or "").strip()
    if not search:
        return []
    try:
        r = _session().get(
            f"{SILENE_BASE_URL}/api/searchTaxon",
            params={"search": search, "limit": int(limit)},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except (requests.RequestException, ValueError):
        return []


def search_commune(search: str, limit: int = 20) -> list[dict[str, Any]]:
    """Autocomplete communes (label + value=code INSEE)."""
    search = (search or "").strip()
    if not search:
        return []
    try:
        r = _session().get(
            f"{SILENE_BASE_URL}/api/searchCommune",
            params={"search": search, "limit": int(limit)},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except (requests.RequestException, ValueError):
        return []


def get_observations_maille(cd_ref: int) -> dict[str, Any]:
    """
    Recupere la repartition par mailles (GeoJSON) pour une espece (cd_ref).
    """
    try:
        r = _session().get(f"{SILENE_BASE_URL}/api/observationsMaille/{int(cd_ref)}", timeout=30)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else {"data": data}
    except (requests.RequestException, ValueError):
        return {"type": "FeatureCollection", "features": []}

