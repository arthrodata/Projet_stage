from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable
import unicodedata

import pandas as pd

from Backend.app.utils.date_filters import parse_any_date


MISSING_VALUE = "Non renseigne"
COUNTRY_ALIASES = {
    "america": "United States",
    "etats unis": "United States",
    "etats-unis": "United States",
    "u s a": "United States",
    "u.s.a": "United States",
    "u.s.a.": "United States",
    "united states of america": "United States",
    "california": "United States",
    "texas": "United States",
    "florida": "United States",
    "new york": "United States",
    "south carolina": "United States",
    "uk": "United Kingdom",
    "u.k": "United Kingdom",
    "u.k.": "United Kingdom",
    "great britain": "United Kingdom",
    "royaume uni": "United Kingdom",
    "royaume-uni": "United Kingdom",
    "united kingdom of great britain and northern ireland": "United Kingdom",
    "england": "United Kingdom",
    "scotland": "United Kingdom",
    "wales": "United Kingdom",
    "northern ireland": "United Kingdom",
    "fr": "France",
    "fra": "France",
    "france metropolitan": "France",
    "france metropolitaine": "France",
    "de": "Germany",
    "deu": "Germany",
    "germany": "Germany",
    "deutschland": "Germany",
    "es": "Spain",
    "esp": "Spain",
    "espana": "Spain",
    "spain": "Spain",
    "it": "Italy",
    "ita": "Italy",
    "italia": "Italy",
    "italie": "Italy",
    "italien": "Italy",
    "be": "Belgium",
    "bel": "Belgium",
    "ch": "Switzerland",
    "che": "Switzerland",
    "suisse": "Switzerland",
    "nl": "Netherlands",
    "nld": "Netherlands",
    "the netherlands": "Netherlands",
    "holland": "Netherlands",
    "at": "Austria",
    "aut": "Austria",
    "osterreich": "Austria",
    "pt": "Portugal",
    "prt": "Portugal",
    "au": "Australia",
    "aus": "Australia",
    "nz": "New Zealand",
    "nzl": "New Zealand",
    "br": "Brazil",
    "bra": "Brazil",
    "brasil": "Brazil",
    "brazilie": "Brazil",
    "za": "South Africa",
    "zaf": "South Africa",
    "cn": "China",
    "chn": "China",
    "china": "China",
    "jp": "Japan",
    "jpn": "Japan",
    "japan": "Japan",
    "kr": "South Korea",
    "kor": "South Korea",
    "south korea": "South Korea",
    "republic of korea": "South Korea",
    "ca": "Canada",
    "can": "Canada",
    "canada": "Canada",
    "cr": "Costa Rica",
    "cri": "Costa Rica",
    "costa rica": "Costa Rica",
    "mx": "Mexico",
    "mex": "Mexico",
    "mexico": "Mexico",
    "pl": "Poland",
    "pol": "Poland",
    "polska": "Poland",
    "ru": "Russia",
    "rus": "Russia",
    "russia": "Russia",
    "tr": "Turkey",
    "tur": "Turkey",
    "turkiye": "Turkey",
    "turkey": "Turkey",
    "tw": "Taiwan",
    "twn": "Taiwan",
    "taiwan": "Taiwan",
    "chinese taipei": "Taiwan",
    "my": "Malaysia",
    "mys": "Malaysia",
    "malaysia": "Malaysia",
    "frasers hill": "Malaysia",
    "fraser s hill": "Malaysia",
    "th": "Thailand",
    "tha": "Thailand",
    "thailand": "Thailand",
    "in": "India",
    "ind": "India",
    "india": "India",
    "id": "Indonesia",
    "idn": "Indonesia",
    "indonesia": "Indonesia",
    "no": "Norway",
    "nor": "Norway",
    "norway": "Norway",
    "se": "Sweden",
    "swe": "Sweden",
    "sweden": "Sweden",
    "hu": "Hungary",
    "hun": "Hungary",
    "hungary": "Hungary",
    "ec": "Ecuador",
    "ecu": "Ecuador",
    "ecuador": "Ecuador",
    "co": "Colombia",
    "col": "Colombia",
    "colombia": "Colombia",
    "cl": "Chile",
    "chl": "Chile",
    "chile": "Chile",
    "pe": "Peru",
    "per": "Peru",
    "peru": "Peru",
    "gambia": "Gambia",
    "gm": "Gambia",
    "gmb": "Gambia",
    "nsw": "Australia",
    "new south wales": "Australia",
    "victoria": "Australia",
    "queensland": "Australia",
    "french guiana": "French Guiana",
    "guyane francaise": "French Guiana",
    "franzosisch guyana": "French Guiana",
    "czesko": "Czechia",
    "cesko": "Czechia",
    "czechia": "Czechia",
    "armenie": "Armenia",
    "armenia": "Armenia",
    "kroatie": "Croatia",
    "croatia": "Croatia",
    "cote d ivoire": "Cote d'Ivoire",
    "cote divoire": "Cote d'Ivoire",
    "ivory coast": "Cote d'Ivoire",
    "georgia": "Georgia",
    "romania": "Romania",
    "rumanien": "Romania",
    "slovenie": "Slovenia",
    "slovenia": "Slovenia",
    "coree du sud": "South Korea",
    "panama": "Panama",
    "danemark": "Denmark",
    "denmark": "Denmark",
    "belgie": "Belgium",
    "greece": "Greece",
    "brésil": "Brazil",
    "bresil": "Brazil",
    "madagascar": "Madagascar",
    "hong kong": "Hong Kong",
    "macau": "Macau",
    "united arab emirates": "United Arab Emirates",
    "uae": "United Arab Emirates",
    "magyarorszag": "Hungary",
    "moth light 102 queen anne bridge road": "United States",
    "suffolk imprecise location to obscure my garden": "United Kingdom",
    "markische schweiz": "Germany",
    "roberts bird sanctuary": "United States",
    "pedregal abajo reserva comunal el siea": "Panama",
    "kemensah hiking trail part 1 kebun pacik sadik": "Malaysia",
    "marica": "Brazil",
    "sitio cumati": "Brazil",
    "rio guapore sao francisco do guapore ro": "Brazil",
    "estacion biologica monte verde": "Costa Rica",
    "mosfellsbr": "Iceland",
    "mosfellsbaer": "Iceland",
}
COUNTRY_TEXT_MARKERS = [
    ("日本", "Japan"),
    ("中国", "China"),
    ("中华人民共和国", "China"),
    ("山东", "China"),
    ("北京", "China"),
    ("上海", "China"),
    ("广东", "China"),
    ("浙江", "China"),
    ("连珠山头", "China"),
    ("杭州", "China"),
    ("南京", "China"),
    ("安徽", "China"),
    ("海南", "China"),
    ("宝华山", "China"),
    ("台州", "China"),
    ("대한민국", "South Korea"),
    ("한국", "South Korea"),
    ("갈재", "South Korea"),
    ("흑성산", "South Korea"),
    ("태조산", "South Korea"),
    ("Россия", "Russia"),
    ("Казахстан", "Kazakhstan"),
    ("ישראל", "Israel"),
    ("צפון הכנרת", "Israel"),
    ("גבעת זאב", "Israel"),
    ("Кыргызстан", "Kyrgyzstan"),
    ("Україна", "Ukraine"),
    ("Грузия", "Georgia"),
    ("Беларусь", "Belarus"),
    ("Южная Африка", "South Africa"),
    ("Япония", "Japan"),
    ("España", "Spain"),
    ("México", "Mexico"),
    ("Österreich", "Austria"),
    ("Rakúsko", "Austria"),
    ("Türkiye", "Turkey"),
    ("Türkei", "Turkey"),
    ("ประเทศไทย", "Thailand"),
    ("Guyane française", "French Guiana"),
    ("台灣", "Taiwan"),
    ("臺灣", "Taiwan"),
    ("台湾", "Taiwan"),
    ("臺中", "Taiwan"),
    ("新莊", "Taiwan"),
    ("大山北月", "Taiwan"),
    ("香港", "Hong Kong"),
    ("澳門", "Macau"),
    ("马来西亚", "Malaysia"),
    ("馬來西亞", "Malaysia"),
    ("秘鲁", "Peru"),
    ("秘魯", "Peru"),
    ("馬達加斯加", "Madagascar"),
    ("마다가스카르", "Madagascar"),
    ("Ελλάδα", "Greece"),
    ("Sharjah", "United Arab Emirates"),
    ("Chocó", "Colombia"),
]
US_STATE_CODES = {
    "ak",
    "al",
    "ar",
    "az",
    "ca",
    "co",
    "ct",
    "dc",
    "de",
    "fl",
    "ga",
    "hi",
    "ia",
    "id",
    "il",
    "in",
    "ks",
    "ky",
    "la",
    "ma",
    "md",
    "me",
    "mi",
    "mn",
    "mo",
    "ms",
    "mt",
    "nc",
    "nd",
    "ne",
    "nh",
    "nj",
    "nm",
    "nv",
    "ny",
    "oh",
    "ok",
    "or",
    "pa",
    "ri",
    "sc",
    "sd",
    "tn",
    "tx",
    "ut",
    "va",
    "vt",
    "wa",
    "wi",
    "wv",
    "wy",
}
STANDARD_COLUMNS = [
    "source_bdd",
    "country",
    "coordinates",
    "eventDate",
    "basisOfRecord",
    "datasetName",
    "family",
    "genus",
    "species",
    "quality_grade",
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
    "quality_grade",
    "status",
]


def clean_text(value: Any, *, missing: str = MISSING_VALUE) -> str:
    if value is None:
        return missing
    if isinstance(value, float) and pd.isna(value):
        return missing
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "null", "not provided"}:
        return missing
    return text


def _country_key(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return (
        ascii_text.casefold()
        .replace("&", " and ")
        .replace(".", "")
        .replace(",", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace("'", " ")
        .replace("’", " ")
        .replace("-", " ")
        .strip()
    )


def normalize_country(value: Any) -> str:
    text = clean_text(value)
    if text == MISSING_VALUE:
        return MISSING_VALUE

    key = " ".join(_country_key(text).split())
    if key.isdigit():
        return MISSING_VALUE
    if key in {"us", "usa"}:
        return "United States"
    if key in {"gb", "gbr"}:
        return "United Kingdom"
    if key in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[key]

    for marker, country in COUNTRY_TEXT_MARKERS:
        if marker in text:
            return country

    searchable = f" {key} "
    for alias, country in sorted(COUNTRY_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if len(alias) >= 5 and f" {alias} " in searchable:
            return country

    return text


def normalize_event_date(value: Any) -> str:
    parsed = parse_any_date(value)
    return parsed.isoformat() if parsed else MISSING_VALUE


def _decimal_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", ".")
    try:
        decimal_value = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    normalized = format(decimal_value.quantize(Decimal("0.000001")), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def normalize_coordinates(value: Any) -> str:
    if value is None:
        return MISSING_VALUE
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "null", "not provided", "non renseigne"}:
        return MISSING_VALUE

    normalized = text.replace(";", ",")
    parts = [part.strip() for part in normalized.split(",") if part.strip()]
    if len(parts) < 2:
        return MISSING_VALUE

    lat = _decimal_text(parts[0])
    lon = _decimal_text(parts[1])
    if lat is None or lon is None:
        return MISSING_VALUE
    return f"{lat}, {lon}"


def normalize_row(row: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for column in STANDARD_COLUMNS:
        value = row.get(column)
        if column == "eventDate":
            normalized[column] = normalize_event_date(value)
        elif column == "country":
            normalized[column] = normalize_country(value)
        elif column == "coordinates":
            normalized[column] = normalize_coordinates(value)
        elif column in {"iucn_assessment_id", "iucn_year", "iucn_scope", "iucn_lookup_status", "redListCategory"}:
            normalized[column] = clean_text(value, missing="")
        elif column == "quality_grade":
            normalized[column] = clean_text(value, missing="")
        else:
            normalized[column] = clean_text(value)

    if not normalized["status"] or normalized["status"] == MISSING_VALUE:
        normalized["status"] = normalized["iucn_status"] or MISSING_VALUE
    if not normalized["redListCategory"]:
        normalized["redListCategory"] = normalized["iucn_status"]
    return normalized


def normalize_rows(rows: Iterable[dict[str, Any]], *, columns: list[str] | None = None) -> list[dict[str, str]]:
    selected_columns = columns or STANDARD_COLUMNS
    return [
        {column: normalized.get(column, MISSING_VALUE) for column in selected_columns}
        for normalized in (normalize_row(row) for row in rows)
    ]


def normalize_dataframe(df: pd.DataFrame, *, columns: list[str] | None = None) -> pd.DataFrame:
    selected_columns = columns or STANDARD_COLUMNS
    if df.empty:
        return pd.DataFrame(columns=selected_columns)
    rows = normalize_rows(df.to_dict(orient="records"), columns=selected_columns)
    return pd.DataFrame(rows).reindex(columns=selected_columns)
