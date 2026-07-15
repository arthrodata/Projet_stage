from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import json
from pathlib import Path
import threading
from typing import Any

import requests


IUCN_API_BASE_URL = "https://api.iucnredlist.org/api/v4"
IUCN_GLOBAL_SCOPE_CODE = "1"
IUCN_EMPTY_STATUS = "Non renseigne"
IUCN_ALLOWED_CODES = {"LC", "NT", "VU", "EN", "CR", "EW", "EX", "DD", "NE"}
IUCN_CACHE_VERSION = "1"
_CACHE_LOCK = threading.RLock()
_DISK_CACHE: dict[str, dict[str, Any]] | None = None


def _cache_path() -> Path:
    configured = os.getenv("IUCN_CACHE_FILE", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "exports" / "iucn_cache.json"


def _cache_key(genus: str, species: str) -> str:
    return f"{genus.strip().casefold()} {species.strip().casefold()}"


def _load_disk_cache() -> dict[str, dict[str, Any]]:
    global _DISK_CACHE
    with _CACHE_LOCK:
        if _DISK_CACHE is not None:
            return _DISK_CACHE

        path = _cache_path()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _DISK_CACHE = {}
            return _DISK_CACHE

        if payload.get("version") != IUCN_CACHE_VERSION or not isinstance(payload.get("items"), dict):
            _DISK_CACHE = {}
            return _DISK_CACHE

        _DISK_CACHE = {
            str(key): value
            for key, value in payload["items"].items()
            if isinstance(value, dict)
        }
        return _DISK_CACHE


def _remember_disk_cache(key: str, result: dict[str, Any]) -> None:
    if result.get("iucn_lookup_status") in {"api_error", "missing_token"}:
        return

    with _CACHE_LOCK:
        cache = _load_disk_cache()
        cache[key] = dict(result)
        path = _cache_path()
        payload = {"version": IUCN_CACHE_VERSION, "items": cache}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_suffix(f"{path.suffix}.tmp")
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tmp_path.replace(path)
        except OSError:
            return


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
    key = _cache_key(genus, species)
    cached = _load_disk_cache().get(key)
    if cached:
        return dict(cached)

    result = dict(_get_iucn_enrichment_cached(token, genus, species))
    _remember_disk_cache(key, result)
    return result


def get_iucn_enrichments(scientific_names: list[str], *, max_workers: int = 8) -> dict[str, dict[str, Any]]:
    """
    Enrichit une liste de noms en parallele.

    Le cache LRU reste utilise par `get_iucn_enrichment`, donc les gros exports
    ne refont pas les appels IUCN deja connus.
    """
    unique_names = list(dict.fromkeys(str(name or "").strip() for name in scientific_names))
    unique_names = [name for name in unique_names if name]
    if not unique_names:
        return {}

    workers = max(1, min(int(max_workers), len(unique_names)))
    out: dict[str, dict[str, Any]] = {}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(get_iucn_enrichment, name): name for name in unique_names}
        for future in as_completed(futures):
            name = futures[future]
            try:
                out[name] = future.result()
            except Exception:
                out[name] = _new_result("api_error")

    return out


def get_iucn_status(scientific_name: str | None) -> str:
    """Compatibility helper used by older callers that only need the status column."""
    return get_iucn_enrichment(scientific_name).get("iucn_status") or IUCN_EMPTY_STATUS
