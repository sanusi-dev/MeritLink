from datetime import date

from django.test import TestCase

from ingestion.services.diff import generate_diffs
from scholarships.models import Scholarship


class GenerateDiffsTests(TestCase):
    """Tests for the diff generation service."""

    def _make_scholarship(self, **overrides) -> Scholarship:
        """Create a Scholarship with known default values."""
        defaults = {
            "title": "Original Title",
            "source_url": "https://example.com/scholarship-1",
            "provider": "Original Provider",
            "application_deadline": date(2026, 6, 15),
            "status": "open",
            "eligible_nationalities": ["Nigeria", "Ghana"],
            "eligible_study_levels": ["Masters"],
            "description": "Original description",
            "min_gpa": 3.0,
            "financial_need_required": False,
        }
        defaults.update(overrides)
        return Scholarship.objects.create(**defaults)

    def test_no_changes_returns_empty_diff(self):
        scholarship = self._make_scholarship()
        new_data = {
            "title": "Original Title",
            "provider": "Original Provider",
            "description": "Original description",
            "status": "open",
            "application_deadline": "2026-06-15",
            "eligible_nationalities": ["Nigeria", "Ghana"],
            "eligible_study_levels": ["Masters"],
            "min_gpa": 3.0,
            "financial_need_required": False,
        }
        self.assertEqual(generate_diffs(scholarship, new_data), {})

    def test_title_changed_shows_old_and_new(self):
        scholarship = self._make_scholarship()
        new_data = {"title": "New Title"}
        diffs = generate_diffs(scholarship, new_data)
        self.assertEqual(diffs["title"], {"old": "Original Title", "new": "New Title"})

    def test_description_changed_shows_old_and_new(self):
        scholarship = self._make_scholarship()
        new_data = {"description": "New description"}
        diffs = generate_diffs(scholarship, new_data)
        self.assertEqual(
            diffs["description"],
            {"old": "Original description", "new": "New description"},
        )

    def test_deadline_changed_shows_iso_strings(self):
        scholarship = self._make_scholarship()
        new_data = {"application_deadline": "2026-07-20"}
        diffs = generate_diffs(scholarship, new_data)
        self.assertEqual(
            diffs["application_deadline"],
            {"old": "2026-06-15", "new": "2026-07-20"},
        )

    def test_list_field_changed_shows_lists(self):
        scholarship = self._make_scholarship()
        new_data = {"eligible_nationalities": ["Nigeria", "Ghana", "Kenya"]}
        diffs = generate_diffs(scholarship, new_data)
        self.assertIn("eligible_nationalities", diffs)
        self.assertEqual(diffs["eligible_nationalities"]["old"], ["Ghana", "Nigeria"])
        self.assertEqual(
            diffs["eligible_nationalities"]["new"], ["Ghana", "Kenya", "Nigeria"]
        )

    def test_list_field_reordered_not_in_diff(self):
        scholarship = self._make_scholarship()
        new_data = {"eligible_nationalities": ["Ghana", "Nigeria"]}
        diffs = generate_diffs(scholarship, new_data)
        self.assertNotIn("eligible_nationalities", diffs)

    def test_list_field_item_added_in_diff(self):
        scholarship = self._make_scholarship()
        new_data = {"eligible_nationalities": ["Nigeria", "Ghana", "Kenya"]}
        diffs = generate_diffs(scholarship, new_data)
        self.assertIn("eligible_nationalities", diffs)
        self.assertEqual(
            diffs["eligible_nationalities"]["new"], ["Ghana", "Kenya", "Nigeria"]
        )

    def test_list_field_item_removed_in_diff(self):
        scholarship = self._make_scholarship()
        new_data = {"eligible_nationalities": ["Nigeria"]}
        diffs = generate_diffs(scholarship, new_data)
        self.assertIn("eligible_nationalities", diffs)
        self.assertEqual(diffs["eligible_nationalities"]["old"], ["Ghana", "Nigeria"])
        self.assertEqual(diffs["eligible_nationalities"]["new"], ["Nigeria"])

    def test_status_changed_in_diff(self):
        scholarship = self._make_scholarship()
        new_data = {"status": "closed"}
        diffs = generate_diffs(scholarship, new_data)
        self.assertEqual(diffs["status"], {"old": "open", "new": "closed"})

    def test_extra_non_scholarship_fields_ignored(self):
        scholarship = self._make_scholarship()
        new_data = {
            "title": "New Title",
            "extraction_confidence": 0.99,
            "amount": "$10,000",
        }
        diffs = generate_diffs(scholarship, new_data)
        self.assertEqual(set(diffs.keys()), {"title"})
        self.assertNotIn("extraction_confidence", diffs)
        self.assertNotIn("amount", diffs)

    def test_protected_fields_ignored(self):
        scholarship = self._make_scholarship()
        new_data = {
            "title": "New Title",
            "id": 9999,
            "created_at": "2030-01-01T00:00:00Z",
            "source_url": "https://evil.example.com/hijack",
            "is_user_submitted": True,
        }
        diffs = generate_diffs(scholarship, new_data)
        self.assertEqual(set(diffs.keys()), {"title"})
        self.assertNotIn("id", diffs)
        self.assertNotIn("created_at", diffs)
        self.assertNotIn("source_url", diffs)
        self.assertNotIn("is_user_submitted", diffs)

    def test_missing_fields_not_compared(self):
        scholarship = self._make_scholarship()
        new_data = {"title": "New Title"}
        diffs = generate_diffs(scholarship, new_data)
        self.assertEqual(set(diffs.keys()), {"title"})
        self.assertNotIn("description", diffs)
        self.assertNotIn("status", diffs)

    def test_numeric_field_changed_in_diff(self):
        scholarship = self._make_scholarship()
        new_data = {"min_gpa": 3.5}
        diffs = generate_diffs(scholarship, new_data)
        self.assertEqual(diffs["min_gpa"], {"old": 3.0, "new": 3.5})

    def test_boolean_field_changed_in_diff(self):
        scholarship = self._make_scholarship()
        new_data = {"financial_need_required": True}
        diffs = generate_diffs(scholarship, new_data)
        self.assertEqual(
            diffs["financial_need_required"], {"old": False, "new": True}
        )

    def test_none_for_field_with_value_in_diff(self):
        scholarship = self._make_scholarship()
        new_data = {"description": None}
        diffs = generate_diffs(scholarship, new_data)
        self.assertEqual(
            diffs["description"], {"old": "Original description", "new": None}
        )

    def test_empty_string_for_field_with_value_in_diff(self):
        scholarship = self._make_scholarship()
        new_data = {"description": ""}
        diffs = generate_diffs(scholarship, new_data)
        self.assertEqual(
            diffs["description"], {"old": "Original description", "new": ""}
        )

    def test_all_fields_changed_all_non_protected_in_diff(self):
        scholarship = Scholarship.objects.create(
            title="Old Title",
            source_url="https://example.com/all-fields",
            provider="Old Provider",
            application_url="https://old.example.com/apply",
            description="Old description",
            short_summary="Old summary",
            application_deadline=date(2026, 6, 15),
            program_start_date=date(2026, 9, 1),
            status="open",
            eligible_nationalities=["Nigeria"],
            eligible_study_levels=["Bachelors"],
            min_gpa=3.0,
            gpa_scale="4.0",
            eligible_fields_of_study=["Engineering"],
            age_limit_max=25,
            financial_need_required=False,
            study_destinations=["USA"],
            funding_details="Old funding",
            funding_amount_approx={"raw": "$5,000"},
            number_of_awards=10,
            eligibility_details="Old eligibility",
            required_documents="Old docs",
            selection_criteria="Old criteria",
            benefits="Old benefits",
            notes_for_applicants="Old notes",
            tags=["old-tag"],
        )
        new_data = {
            "title": "New Title",
            "provider": "New Provider",
            "application_url": "https://new.example.com/apply",
            "description": "New description",
            "short_summary": "New summary",
            "application_deadline": "2026-07-20",
            "program_start_date": "2026-10-01",
            "status": "closed",
            "eligible_nationalities": ["Ghana"],
            "eligible_study_levels": ["Masters"],
            "min_gpa": 3.5,
            "gpa_scale": "5.0",
            "eligible_fields_of_study": ["Medicine"],
            "age_limit_max": 30,
            "financial_need_required": True,
            "study_destinations": ["UK"],
            "funding_details": "New funding",
            "funding_amount_approx": {"raw": "$10,000"},
            "number_of_awards": 20,
            "eligibility_details": "New eligibility",
            "required_documents": "New docs",
            "selection_criteria": "New criteria",
            "benefits": "New benefits",
            "notes_for_applicants": "New notes",
            "tags": ["new-tag"],
        }
        diffs = generate_diffs(scholarship, new_data)
        self.assertEqual(set(diffs.keys()), set(new_data.keys()))
