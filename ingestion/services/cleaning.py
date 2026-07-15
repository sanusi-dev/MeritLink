"""
Automated cleaning and validation pipeline.
These rules run on every extraction (new and updates).
Refine these heavily once you have real data.
"""
import re
from datetime import date, datetime
from typing import Any


_DATE_PARSE_FORMATS = (
    "%Y-%m-%d",
    "%d %B %Y",
    "%B %d, %Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%d %b %Y",
    "%b %d, %Y",
    "%m/%d/%Y",
    "%d %B, %Y",
    "%B %d %Y",
)

_COUNTRY_MAP = {
    "uk": "United Kingdom",
    "united kingdom of great britain and northern ireland": "United Kingdom",
    "great britain": "United Kingdom",
    "usa": "United States",
    "us": "United States",
    "u.s.a": "United States",
    "u.s.a.": "United States",
    "united states of america": "United States",
    "united states": "United States",
    "nigeria": "Nigeria",
    "ghana": "Ghana",
    "kenya": "Kenya",
    "south africa": "South Africa",
    "south africa ": "South Africa",
    "egypt": "Egypt",
    "ethiopia": "Ethiopia",
    "tanzania": "Tanzania",
    "uganda": "Uganda",
    "rwanda": "Rwanda",
    "cameroon": "Cameroon",
    "senegal": "Senegal",
    "morocco": "Morocco",
    "algeria": "Algeria",
    "tunisia": "Tunisia",
    "india": "India",
    "china": "China",
    "japan": "Japan",
    "south korea": "South Korea",
    "korea": "South Korea",
    "germany": "Germany",
    "france": "France",
    "netherlands": "Netherlands",
    "australia": "Australia",
    "canada": "Canada",
    "new zealand": "New Zealand",
    "all": "all",
    "all countries": "all",
    "any": "all",
    "worldwide": "all",
    "international": "all",
    "global": "all",
}

_LEVEL_MAP = {
    "undergraduate": "Bachelors",
    "bachelor": "Bachelors",
    "bachelors": "Bachelors",
    "bsc": "Bachelors",
    "b.sc": "Bachelors",
    "b.sc.": "Bachelors",
    "ba": "Bachelors",
    "b.a": "Bachelors",
    "b.a.": "Bachelors",
    "btech": "Bachelors",
    "b.eng": "Bachelors",
    "b.eng.": "Bachelors",
    "postgraduate": "Masters",
    "master": "Masters",
    "masters": "Masters",
    "master's": "Masters",
    "msc": "Masters",
    "m.sc": "Masters",
    "m.sc.": "Masters",
    "ma": "Masters",
    "m.a": "Masters",
    "m.a.": "Masters",
    "mtech": "Masters",
    "m.eng": "Masters",
    "m.eng.": "Masters",
    "mba": "Masters",
    "phd": "PhD",
    "ph.d": "PhD",
    "ph.d.": "PhD",
    "doctorate": "PhD",
    "doctoral": "PhD",
    "postdoc": "Postdoc",
    "postdoctoral": "Postdoc",
    "diploma": "Diploma",
    "certificate": "Certificate",
    "foundation": "Foundation",
    "high school": "High School",
    "secondary": "High School",
}

_CURRENCY_SYMBOL_MAP = {
    "$": "USD",
    "£": "GBP",
    "€": "EUR",
    "₦": "NGN",
}


def clean_extracted_data(raw: dict) -> dict:
    """
    Main entry point. Takes raw LLM output and returns cleaned/normalized version.

    With Pydantic's ScholarshipSchema, the input dict is guaranteed to have
    all schema keys present. Non-Optional str fields may still be empty strings,
    Optional fields may be None, and list fields are always List[str].
    This function normalizes values, not keys.
    """
    cleaned = raw.copy()

    if deadline := raw.get("application_deadline"):
        cleaned["application_deadline"] = _normalize_date(deadline)

    if start_date := raw.get("program_start_date"):
        cleaned["program_start_date"] = _normalize_date(start_date)

    for field in ("eligible_nationalities", "eligible_study_levels",
                  "eligible_fields_of_study", "study_destinations", "tags"):
        if val := raw.get(field):
            cleaned[field] = _normalize_list(val)

    if val := cleaned.get("eligible_nationalities"):
        cleaned["eligible_nationalities"] = _normalize_countries(val)
    if val := cleaned.get("study_destinations"):
        cleaned["study_destinations"] = _normalize_countries(val)
    if val := cleaned.get("eligible_study_levels"):
        cleaned["eligible_study_levels"] = _normalize_study_levels(val)

    if amount := raw.get("funding_amount_approx"):
        cleaned["funding_amount_approx"] = _parse_amount(amount)

    for text_field in ("description", "eligibility_details", "benefits",
                       "short_summary", "funding_details", "required_documents",
                       "selection_criteria", "notes_for_applicants"):
        if val := raw.get(text_field):
            cleaned[text_field] = _clean_text(val)

    cleaned.setdefault("status", "open")

    _run_quality_gates(cleaned)

    _confidence_map = {"ok": 1.0, "warn": 0.6, "fail": 0.2}
    cleaned["extraction_confidence"] = _confidence_map.get(
        cleaned["_quality_status"], 0.5
    )

    return cleaned


def _strip_ordinal_suffix(text: str) -> str:
    """Remove ordinal suffixes (st, nd, rd, th) from day numbers in a string."""
    return re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text)


def _normalize_date(value: Any) -> str | None:
    """
    Parse a value into an ISO date string (YYYY-MM-DD).

    Tries multiple date formats, handling ordinal suffixes (1st, 2nd, etc.).
    Returns None for empty input, the stripped original string if no format
    matches, and ISO strings for date/datetime objects.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    if not value:
        return None
    cleaned = _strip_ordinal_suffix(value)
    for fmt in _DATE_PARSE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return value


def _normalize_list(value: Any) -> list:
    """
    Split, trim, and filter a list or comma-separated string into clean items.

    Pydantic guarantees list fields arrive as List[str]; the comma-split
    string branch is a defensive fallback for non-LLM ingestion sources.
    """
    if isinstance(value, list):
        return [str(v).strip() for v in value if v]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def _normalize_countries(countries: list) -> list:
    """
    Standardize country names to canonical forms.

    Maps common variants (UK, USA, etc.) to canonical names, title-cases
    unknown countries, and deduplicates the result.
    """
    if not isinstance(countries, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for country in countries:
        key = str(country).strip().lower()
        canonical = _COUNTRY_MAP.get(key)
        if canonical is None:
            canonical = str(country).strip().title()
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result


def _normalize_study_levels(levels: list) -> list:
    """
    Standardize study level names to canonical forms.

    Maps common variants (BSc, MSc, PhD, etc.) to canonical names,
    title-cases unknown levels, and deduplicates the result.
    """
    if not isinstance(levels, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for level in levels:
        key = str(level).strip().lower()
        canonical = _LEVEL_MAP.get(key)
        if canonical is None:
            canonical = str(level).strip().title()
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result


def _to_number(value: str) -> int | float:
    """Convert a numeric string with commas to a number."""
    cleaned = value.replace(",", "")
    if "." in cleaned:
        return float(cleaned)
    return int(cleaned)


_FUNDING_KEYS = ("type", "amount_usd", "max_amount_usd", "stipend_usd", "currency", "raw")


def _extract_amount_result(raw: str, lower: str, amounts: list) -> dict:
    """Build a structured result dict matching FundingAmountDetails keys."""
    result: dict[str, Any] = dict.fromkeys(_FUNDING_KEYS, None)
    result["raw"] = raw
    has_full_tuition = "full tuition" in lower or "full-tuition" in lower
    has_stipend = "stipend" in lower
    has_up_to = "up to" in lower

    if has_full_tuition and has_stipend and amounts:
        symbol, amount = amounts[0]
        result["type"] = "full_tuition_plus_stipend"
        result["currency"] = _CURRENCY_SYMBOL_MAP.get(symbol, "Unknown")
        if result["currency"] == "USD":
            result["stipend_usd"] = _to_number(amount)
    elif has_full_tuition:
        result["type"] = "full_tuition"
    elif has_up_to and amounts:
        symbol, amount = amounts[0]
        result["currency"] = _CURRENCY_SYMBOL_MAP.get(symbol, "Unknown")
        if result["currency"] == "USD":
            result["max_amount_usd"] = _to_number(amount)
    elif amounts:
        symbol, amount = amounts[0]
        result["currency"] = _CURRENCY_SYMBOL_MAP.get(symbol, "Unknown")
        if result["currency"] == "USD":
            result["amount_usd"] = _to_number(amount)

    return result


def _parse_amount(value: Any) -> dict:
    """
    Parse a funding amount from a dict or string.

    Dicts (the normal path from Pydantic/FundingAmountDetails) are passed
    through unchanged. Strings are parsed via regex for non-LLM ingestion
    sources (manual entry, CSV import) — currency symbols and amounts are
    extracted and mapped to FundingAmountDetails keys. ``amount_usd``,
    ``max_amount_usd``, and ``stipend_usd`` are only populated when the
    detected currency is USD; non-USD amounts preserve ``currency`` and
    ``raw`` only.
    """
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return dict.fromkeys(_FUNDING_KEYS, None) | {"raw": str(value)}
    raw = value.strip()
    if not raw:
        return dict.fromkeys(_FUNDING_KEYS, None) | {"raw": raw}
    lower = raw.lower()
    amounts = re.findall(r"([$£€₦])\s*([\d,]+(?:\.\d+)?)", raw)
    return _extract_amount_result(raw, lower, amounts)


def _clean_text(text: str) -> str:
    """Strip, collapse whitespace, remove boilerplate phrases, and cap at 8000 chars."""
    if not text:
        return ""
    text = text.strip()
    text = " ".join(text.split())
    boilerplate = ["apply now", "click here", "for more information visit"]
    lower = text.lower()
    for phrase in boilerplate:
        if phrase in lower:
            text = text.replace(phrase, "").strip()
    return text[:8000]


def _run_quality_gates(cleaned: dict) -> None:
    """
    Run quality checks on cleaned data and add quality status.

    Pydantic guarantees title, source_url, and application_deadline are
    present as str keys. The real failure mode is empty-string values,
    not absent keys — the falsy check catches both.

    Empty title or source_url results in a 'fail' status.
    Empty deadline or study levels results in a 'warn' status only.
    All present and non-empty results in an 'ok' status.
    """
    issues: list[str] = []
    if not cleaned.get("title"):
        issues.append("Missing title")
    if not cleaned.get("source_url"):
        issues.append("Missing source_url")
    if not cleaned.get("application_deadline"):
        issues.append("Missing application_deadline")
    if not cleaned.get("eligible_study_levels"):
        issues.append("Missing eligible_study_levels")

    if issues:
        cleaned["_quality_issues"] = issues
        has_hard_fail = any("title" in i or "source_url" in i for i in issues)
        cleaned["_quality_status"] = "warn" if not has_hard_fail else "fail"
    else:
        cleaned["_quality_status"] = "ok"
