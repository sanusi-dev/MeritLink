"""
Smart deduplication helpers.
Used by the script and management commands.
"""
from typing import Optional
from scholarships.models import Scholarship


def find_existing_record(source_url: str) -> Optional[Scholarship]:
    """
    Returns existing live Scholarship for this URL if present.
    Extend later with fuzzy title + provider matching.
    """
    try:
        return Scholarship.objects.get(source_url=source_url)
    except Scholarship.DoesNotExist:
        return None


def is_duplicate(raw_data: dict) -> bool:
    """Additional fuzzy checks can go here."""
    return False
