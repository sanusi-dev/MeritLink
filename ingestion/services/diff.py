"""
Diff generation service — compares a live Scholarship against new cleaned data.
Used by the re-check flow to show reviewers what changed.
"""
from datetime import date, datetime
from typing import Any

from django.db import models as django_models

from scholarships.models import Scholarship


_VALID_SCHOLARSHIP_FIELDS = frozenset(
    f.name for f in Scholarship._meta.fields
)

_DATE_FIELDS = frozenset(
    f.name for f in Scholarship._meta.fields
    if isinstance(f, django_models.DateField)
)

_LIST_FIELDS = frozenset(
    f.name for f in Scholarship._meta.fields
    if isinstance(f, django_models.JSONField)
    and isinstance(f.get_default(), list)
)

_PROTECTED_FIELDS = frozenset({
    "id",
    "created_at",
    "updated_at",
    "last_verified",
    "is_user_submitted",
    "source_url",
})


def _normalize_date_value(value: Any) -> str | None:
    """Normalize a date value to an ISO date string, or None when empty."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _normalize_list_value(value: Any) -> list:
    """Normalize a list value to a sorted list for order-independent comparison."""
    if value is None:
        return []
    if isinstance(value, list):
        return sorted(value)
    return [value]


def _normalize_value(field_name: str, value: Any) -> Any:
    """Normalize a value based on its field type for comparison and display."""
    if field_name in _DATE_FIELDS:
        return _normalize_date_value(value)
    if field_name in _LIST_FIELDS:
        return _normalize_list_value(value)
    return value


def generate_diffs(scholarship: Scholarship, new_data: dict) -> dict[str, dict]:
    """
    Compare a live Scholarship record against new cleaned_data.

    Returns a dict keyed by field name, where each value is:
    {"old": <current value>, "new": <new value>}

    Only fields that differ are included. Fields present in new_data
    but not on the Scholarship model are ignored. Fields not present
    in new_data are not compared (no change assumed).

    Date fields are compared as ISO date strings for readability.
    List fields are compared as sorted lists (order-independent comparison).
    """
    diffs: dict[str, dict] = {}
    for key, new_value in new_data.items():
        if key not in _VALID_SCHOLARSHIP_FIELDS:
            continue
        if key in _PROTECTED_FIELDS:
            continue
        old_value = getattr(scholarship, key)
        old_norm = _normalize_value(key, old_value)
        new_norm = _normalize_value(key, new_value)
        if old_norm != new_norm:
            diffs[key] = {"old": old_norm, "new": new_norm}
    return diffs
