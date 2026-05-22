import os
from typing import Any, Optional

import requests
from urllib.parse import quote


# Service IUCN : récupère le statut de conservation (Red List) d'une espèce.
# Le token API ne doit jamais être écrit dans le code : on le lit depuis une variable
# d'environnement (IUCN_TOKEN).

IUCN_API_BASE_URL = "https://apiv4.iucnredlist.org/api/v4"

# Codes attendus (IUCN Red List categories)
_ALLOWED_CODES = {"LC", "NT", "VU", "EN", "CR", "EW", "EX", "DD", "NE"}


def _normalize_status(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    upper = text.upper()
    if upper in _ALLOWED_CODES:
        return upper

    if upper in {"NOT EVALUATED", "NOT_EVALUATED"}:
        return "NE"
    if upper in {"DATA DEFICIENT", "DATA_DEFICIENT"}:
        return "DD"

    mapping = {
        "LEAST CONCERN": "LC",
        "NEAR THREATENED": "NT",
        "VULNERABLE": "VU",
        "ENDANGERED": "EN",
        "CRITICALLY ENDANGERED": "CR",
        "EXTINCT IN THE WILD": "EW",
        "EXTINCT": "EX",
    }
    return mapping.get(upper)


def _extract_status(payload: Any) -> Optional[str]:
    """
    Parsing robuste : la structure peut varier, donc on teste plusieurs clés.
    """
    if payload is None:
        return None

    if isinstance(payload, list):
        for item in payload:
            status = _extract_status(item)
            if status:
                return status
        return None

    if not isinstance(payload, dict):
        return _normalize_status(payload)

    for key in ("red_list_category", "category", "code"):
        status = _normalize_status(payload.get(key))
        if status:
            return status

    for container_key in ("assessments", "result"):
        if container_key in payload:
            status = _extract_status(payload.get(container_key))
            if status:
                return status

    for _, value in payload.items():
        status = _extract_status(value)
        if status:
            return status

    return None


def get_iucn_status(species_name: str) -> str:
    """
    Retourne le statut IUCN (code) pour un nom scientifique d'espèce.
    - "Non renseigné" si le nom est vide
    - "Non vérifié" si le token IUCN_TOKEN n'est pas défini
    - "NE" si l'espèce n'est pas évaluée / non trouvée
    - "NE" si erreur technique (réseau/API)
    """
    name = (species_name or "").strip()
    if not name:
        return "Non renseigné"

    token = os.getenv("IUCN_TOKEN")
    if not token:
        return "Non vérifié"

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }

    session = requests.Session()
    # Important : on ignore les variables proxy du système/environnement.
    session.trust_env = False

    taxa_url = f"{IUCN_API_BASE_URL}/taxa/scientific_name/{quote(name)}"
    fallback_endpoints = [
        f"{IUCN_API_BASE_URL}/species/{quote(name)}",
        f"{IUCN_API_BASE_URL}/species/name/{quote(name)}",
    ]

    def get_json(url: str) -> Optional[Any]:
        try:
            resp = session.get(url, headers=headers, timeout=20)
            if resp.status_code in (401, 403):
                resp = session.get(url, params={"token": token}, timeout=20)

            if resp.status_code == 404:
                return None
            if not resp.ok:
                return None
            return resp.json()
        except (requests.RequestException, ValueError):
            # Erreur réseau / parsing JSON -> on n'échoue pas l'export,
            # on considère le statut comme non récupérable.
            return None

    try:
        payload = get_json(taxa_url)
        if payload is not None:
            status = _extract_status(payload)
            if status:
                return status

            assessment_id: Optional[str] = None
            candidates = payload if isinstance(payload, list) else [payload]
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                for key in ("assessment_id", "assessmentId", "id"):
                    value = item.get(key)
                    if value is not None and str(value).strip():
                        assessment_id = str(value).strip()
                        break
                if assessment_id:
                    break

            if assessment_id:
                assessment_url = f"{IUCN_API_BASE_URL}/assessment/{quote(assessment_id)}"
                assessment_payload = get_json(assessment_url)
                status = _extract_status(assessment_payload)
                return status or "NE"

        for url in fallback_endpoints:
            payload = get_json(url)
            status = _extract_status(payload)
            if status:
                return status

        return "NE"
    except Exception:
        # Défaut robuste : éviter de remplir le CSV avec un message technique.
        # Si l'appel IUCN échoue, on retourne un code standard.
        return "NE"
