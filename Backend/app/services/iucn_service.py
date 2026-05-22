from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import requests


IUCN_API_BASE_URL = "https://api.iucnredlist.org/api/v4"
IUCN_GLOBAL_SCOPE_CODE = "1"
IUCN_EMPTY_STATUS = "Non renseigne"
IUCN_ALLOWED_CODES = {"LC", "NT", "VU", "EN", "CR", "EW", "EX", "DD", "NE"}


def split_species_name(scientific_name: str | None) -> tuple[str, str] | None:
    """Return the genus/species pair required by the IUCN scientific-name endpoint."""
    tokens = str(scientific_name or "").strip().split()
    if len(tokens) < 2:
        return None

    genus, species = tokens[:2]
    if not genus or not species or not species[:1].islower():
        return None

    return genus, species


def _new_result(lookup_status: str, **values: Any) -> dict[str, Any]:
    result = {
        "iucn_status": None,
        "iucn_lookup_status": lookup_status,
        "iucn_assessment_id": None,
        "iucn_year": None,
        "iucn_scope": None,
    }
    result.update(values)
    return result


def _is_global_scope(assessment: dict[str, Any]) -> bool:
    for scope in assessment.get("scopes") or []:
        if str(scope.get("code", "")).strip() == IUCN_GLOBAL_SCOPE_CODE:
            return True

        description = scope.get("description") or {}
        if str(description.get("en", "")).strip().casefold() == "global":
            return True

    return False


def _status_code(assessment: dict[str, Any]) -> str | None:
    status = str(assessment.get("red_list_category_code") or "").strip().upper()
    return status if status in IUCN_ALLOWED_CODES else None


def _select_global_latest_assessment(payload: dict[str, Any]) -> dict[str, Any] | None:
    assessments = payload.get("assessments") or []
    candidates = [
        assessment
        for assessment in assessments
        if isinstance(assessment, dict)
        and assessment.get("latest") is True
        and _is_global_scope(assessment)
        and _status_code(assessment)
    ]

    if not candidates:
        return None

    return max(candidates, key=lambda item: str(item.get("year_published") or ""))


@lru_cache(maxsize=2048)
def _get_iucn_enrichment_cached(token: str, genus: str, species: str) -> dict[str, Any]:
    session = requests.Session()
    session.trust_env = False

    try:
        response = session.get(
            f"{IUCN_API_BASE_URL}/taxa/scientific_name",
            params={"genus_name": genus, "species_name": species},
            headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
            timeout=20,
        )
        if response.status_code == 404:
            return _new_result("not_found")

        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return _new_result("api_error")

    if not isinstance(payload, dict):
        return _new_result("api_error")

    assessment = _select_global_latest_assessment(payload)
    if not assessment:
        return _new_result("no_global_assessment")

    return _new_result(
        "ok",
        iucn_status=_status_code(assessment),
        iucn_assessment_id=assessment.get("assessment_id"),
        iucn_year=assessment.get("year_published"),
        iucn_scope="Global",
    )


def get_iucn_enrichment(scientific_name: str | None) -> dict[str, Any]:
    taxon = split_species_name(scientific_name)
    if not taxon:
        return _new_result("invalid_species_name")

    token = os.getenv("IUCN_TOKEN", "").strip()
    if not token:
        return _new_result("missing_token")

    genus, species = taxon
    return dict(_get_iucn_enrichment_cached(token, genus, species))


def get_iucn_status(scientific_name: str | None) -> str:
    """Compatibility helper used by older callers that only need the status column."""
    return get_iucn_enrichment(scientific_name).get("iucn_status") or IUCN_EMPTY_STATUS
