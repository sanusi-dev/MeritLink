"""
Automated cleaning and validation pipeline.
These rules run on every extraction (new and updates).
Refine these heavily once you have real data.
"""
from typing import Any


def clean_extracted_data(raw: dict) -> dict:
    """
    Main entry point. Takes raw LLM output and returns cleaned/normalized version.
    """
    cleaned = raw.copy()

    # 1. Date normalization (very important)
    if deadline := raw.get("application_deadline"):
        cleaned["application_deadline"] = _normalize_date(deadline)

    # 2. Normalize lists
    for field in ("eligible_nationalities", "eligible_study_levels",
                  "eligible_fields_of_study", "study_destinations", "tags"):
        if val := raw.get(field):
            cleaned[field] = _normalize_list(val)

    # 3. Basic amount parsing (stub)
    if amount := raw.get("funding_amount_approx") or raw.get("amount"):
        cleaned["funding_amount_approx"] = _parse_amount(amount)

    # 4. Text cleanup
    for text_field in ("description", "eligibility_details", "benefits"):
        if val := raw.get(text_field):
            cleaned[text_field] = _clean_text(val)

    # 5. Quality gates / defaults
    cleaned.setdefault("status", "open")

    # Add confidence if missing
    if "extraction_confidence" not in cleaned:
        cleaned["extraction_confidence"] = raw.get("confidence", 0.7)

    return cleaned


def _normalize_date(value: Any) -> str | None:
    """Very naive date normalizer. Replace with dateparser or LLM-assisted later."""
    if not value:
        return None
    if isinstance(value, str):
        # TODO: use dateparser or similar
        return value.strip()
    return str(value)


def _normalize_list(value: Any) -> list:
    if isinstance(value, list):
        return [str(v).strip() for v in value if v]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def _parse_amount(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    return {"raw": str(value)}


def _clean_text(text: str) -> str:
    if not text:
        return ""
    # Basic cleanup
    text = text.strip()
    text = " ".join(text.split())  # collapse whitespace
    # Remove very common boilerplate
    boilerplate = ["apply now", "click here", "for more information visit"]
    lower = text.lower()
    for phrase in boilerplate:
        if phrase in lower:
            text = text.replace(phrase, "").strip()
    return text[:8000]  # safety cap
