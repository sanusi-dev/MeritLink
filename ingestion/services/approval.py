"""
Approval service — bridges the review layer to live Scholarship records.

When a ReviewItem is approved, this service creates or updates the
corresponding Scholarship with data from cleaned_data. All other
pipeline code (admin actions, management commands, views) should go
through `approve_review_item` rather than calling `mark_approved` directly.
"""
from datetime import date, datetime
from typing import Any

from django.db import models as django_models
from django.utils import timezone

from scholarships.models import Scholarship
from ..models import ReviewItem


_VALID_SCHOLARSHIP_FIELDS = frozenset(f.name for f in Scholarship._meta.fields)

_DATE_FIELDS = frozenset(
    f.name for f in Scholarship._meta.fields
    if isinstance(f, django_models.DateField)
)

_PROTECTED_FIELDS = frozenset({
    "id",
    "created_at",
    "updated_at",
    "last_verified",
    "is_user_submitted",
})

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
)


def _parse_date(value: Any) -> date | None:
    """Parse a value into a date object, returning None when not parseable."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    for fmt in _DATE_PARSE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _resolve_target(review_item: ReviewItem) -> Scholarship:
    """Return the Scholarship instance to populate for this review item."""
    if review_item.review_type == "update":
        return Scholarship.objects.get(source_url=review_item.source_url)
    return Scholarship(source_url=review_item.source_url)


def _apply_cleaned_data(scholarship: Scholarship, data: dict) -> None:
    """Set only valid, non-protected Scholarship fields from a data dict."""
    for key, value in data.items():
        if key not in _VALID_SCHOLARSHIP_FIELDS or key in _PROTECTED_FIELDS:
            continue
        if key in _DATE_FIELDS:
            parsed = _parse_date(value)
            if parsed is None:
                continue
            value = parsed
        setattr(scholarship, key, value)


def approve_review_item(
    review_item: ReviewItem,
    overrides: dict | None = None,
) -> Scholarship:
    """
    Approve a pending ReviewItem, creating or updating its Scholarship.

    For a "new" review item a Scholarship is created from cleaned_data.
    For an "update" review item the existing Scholarship matching
    ``source_url`` is loaded and updated with cleaned_data.

    Only keys that correspond to real Scholarship model fields are applied;
    anything else in cleaned_data (e.g. ``extraction_confidence``,
    ``amount``) is silently ignored. Date strings are parsed into
    ``date`` objects before assignment.

    ``source_url`` is always taken from the ReviewItem (never from
    cleaned_data), ``last_verified`` is stamped to now, and
    ``is_user_submitted`` is copied from the ReviewItem.

    Args:
        review_item: A ReviewItem whose status is "pending".
        overrides: Optional reviewer edits applied on top of cleaned_data
            before saving. Same key restrictions as cleaned_data apply.

    Returns:
        The created or updated Scholarship.

    Raises:
        ValueError: If ``review_item.status`` is not "pending".
        Scholarship.DoesNotExist: If ``review_type`` is "update" and no
            Scholarship exists with the review item's ``source_url``.
    """
    if review_item.status != "pending":
        raise ValueError(
            f"ReviewItem {review_item.pk} is not pending "
            f"(status={review_item.status!r}); cannot approve."
        )

    scholarship = _resolve_target(review_item)

    merged_data: dict[str, Any] = dict(review_item.cleaned_data or {})
    if overrides:
        merged_data.update(overrides)
    _apply_cleaned_data(scholarship, merged_data)

    scholarship.source_url = review_item.source_url
    scholarship.last_verified = timezone.now()
    scholarship.is_user_submitted = review_item.is_user_submitted
    scholarship.save()
    review_item.mark_approved()
    return scholarship
