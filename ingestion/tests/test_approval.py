from datetime import date
from unittest.mock import Mock

from django.test import TestCase

from ingestion.admin import ReviewItemAdmin
from ingestion.models import ReviewItem
from ingestion.services.approval import approve_review_item, _parse_date
from scholarships.models import Scholarship


def make_review_item(**overrides):
    """Create a pending ReviewItem with sensible default cleaned_data."""
    defaults = {
        "source_url": "https://example.com/scholarship",
        "review_type": "new",
        "raw_extraction": {},
        "cleaned_data": {
            "title": "Test Scholarship",
            "provider": "Test Provider",
            "description": "A test scholarship",
            "status": "open",
            "eligible_nationalities": ["NG", "KE"],
            "extraction_confidence": 0.95,
            "amount": "$5,000",
        },
        "is_user_submitted": False,
    }
    defaults.update(overrides)
    return ReviewItem.objects.create(**defaults)


class ApproveNewItemTests(TestCase):
    def test_creates_scholarship_with_correct_fields(self):
        item = make_review_item()
        scholarship = approve_review_item(item)
        scholarship.refresh_from_db()

        self.assertEqual(scholarship.title, "Test Scholarship")
        self.assertEqual(scholarship.provider, "Test Provider")
        self.assertEqual(scholarship.description, "A test scholarship")
        self.assertEqual(scholarship.status, "open")
        self.assertEqual(scholarship.eligible_nationalities, ["NG", "KE"])
        self.assertEqual(Scholarship.objects.count(), 1)

    def test_approve_creates_scholarship_with_minimal_fields(self):
        item = make_review_item(cleaned_data={"title": "Minimal Scholarship"})
        scholarship = approve_review_item(item)
        self.assertEqual(scholarship.title, "Minimal Scholarship")
        self.assertEqual(scholarship.source_url, item.source_url)
        self.assertEqual(scholarship.provider, "")
        self.assertEqual(Scholarship.objects.count(), 1)

    def test_sets_last_verified_to_now(self):
        from django.utils import timezone
        before = timezone.now()
        item = make_review_item()
        scholarship = approve_review_item(item)
        after = timezone.now()

        self.assertIsNotNone(scholarship.last_verified)
        self.assertGreaterEqual(scholarship.last_verified, before)
        self.assertLessEqual(scholarship.last_verified, after)

    def test_sets_is_user_submitted_from_review_item(self):
        item = make_review_item(is_user_submitted=True)
        scholarship = approve_review_item(item)
        self.assertTrue(scholarship.is_user_submitted)

    def test_marks_review_item_status_and_reviewed_at(self):
        from django.utils import timezone
        before = timezone.now()
        item = make_review_item()
        approve_review_item(item)
        item.refresh_from_db()

        self.assertEqual(item.status, "approved")
        self.assertIsNotNone(item.reviewed_at)
        self.assertGreaterEqual(item.reviewed_at, before)

    def test_source_url_preserved_on_created_scholarship(self):
        item = make_review_item(
            source_url="https://provider.example.org/award"
        )
        scholarship = approve_review_item(item)
        self.assertEqual(scholarship.source_url, item.source_url)

    def test_source_url_in_cleaned_data_ignored_for_source_url(self):
        item = make_review_item(
            cleaned_data={
                "title": "Conflicting URL",
                "source_url": "https://evil.example.com/hijack",
            }
        )
        scholarship = approve_review_item(item)
        self.assertEqual(scholarship.source_url, item.source_url)
        self.assertNotEqual(scholarship.source_url, "https://evil.example.com/hijack")


class ApproveUpdateItemTests(TestCase):
    def setUp(self):
        self.existing = Scholarship.objects.create(
            title="Old Title",
            source_url="https://example.com/award",
            provider="Old Provider",
            description="Old description",
        )

    def test_updates_existing_scholarship(self):
        item = make_review_item(
            source_url="https://example.com/award",
            review_type="update",
            cleaned_data={
                "title": "New Title",
                "provider": "New Provider",
                "description": "New description",
            },
        )
        scholarship = approve_review_item(item)
        scholarship.refresh_from_db()

        self.assertEqual(scholarship.pk, self.existing.pk)
        self.assertEqual(scholarship.title, "New Title")
        self.assertEqual(scholarship.provider, "New Provider")
        self.assertEqual(scholarship.description, "New description")
        self.assertEqual(Scholarship.objects.count(), 1)

    def test_update_without_existing_raises_does_not_exist(self):
        item = make_review_item(
            source_url="https://nope.example.com/missing",
            review_type="update",
            cleaned_data={"title": "Ghost"},
        )
        with self.assertRaises(Scholarship.DoesNotExist):
            approve_review_item(item)

    def test_update_does_not_mark_approved_on_failure(self):
        item = make_review_item(
            source_url="https://nope.example.com/missing",
            review_type="update",
            cleaned_data={"title": "Ghost"},
        )
        with self.assertRaises(Scholarship.DoesNotExist):
            approve_review_item(item)
        item.refresh_from_db()
        self.assertEqual(item.status, "pending")
        self.assertIsNone(item.reviewed_at)


class ApproveValidationTests(TestCase):
    def test_non_pending_raises_value_error(self):
        item = make_review_item()
        approve_review_item(item)
        with self.assertRaises(ValueError):
            approve_review_item(item)

    def test_rejected_item_raises_value_error(self):
        item = make_review_item()
        item.mark_rejected()
        with self.assertRaises(ValueError):
            approve_review_item(item)

    def test_invalid_keys_in_cleaned_data_ignored(self):
        item = make_review_item(
            cleaned_data={
                "title": "Real",
                "extraction_confidence": 0.1,
                "confidence": 0.2,
                "amount": "$1,000",
                "totally_made_up_field": "boom",
                "object_id": 9999,
            }
        )
        scholarship = approve_review_item(item)
        self.assertEqual(scholarship.title, "Real")
        self.assertEqual(scholarship.funding_amount_approx, {})
        self.assertFalse(hasattr(scholarship, "totally_made_up_field"))


class DateParsingTests(TestCase):
    def test_parse_iso_format(self):
        self.assertEqual(_parse_date("2026-06-15"), date(2026, 6, 15))

    def test_parse_d_month_year(self):
        self.assertEqual(_parse_date("15 June 2026"), date(2026, 6, 15))

    def test_parse_month_d_comma_year(self):
        self.assertEqual(_parse_date("June 15, 2026"), date(2026, 6, 15))

    def test_parse_slash_format(self):
        self.assertEqual(_parse_date("15/06/2026"), date(2026, 6, 15))

    def test_parse_already_date(self):
        d = date(2025, 1, 2)
        self.assertEqual(_parse_date(d), d)

    def test_parse_none_and_empty(self):
        self.assertIsNone(_parse_date(None))
        self.assertIsNone(_parse_date(""))
        self.assertIsNone(_parse_date("   "))

    def test_parse_unparseable(self):
        self.assertIsNone(_parse_date("not a date"))

    def test_deadline_and_start_date_strings_parsed_to_dates(self):
        item = make_review_item(
            cleaned_data={
                "title": "Dated",
                "application_deadline": "2026-06-15",
                "program_start_date": "September 1, 2026",
            }
        )
        scholarship = approve_review_item(item)
        self.assertEqual(scholarship.application_deadline, date(2026, 6, 15))
        self.assertEqual(scholarship.program_start_date, date(2026, 9, 1))

    def test_empty_date_string_skips_field(self):
        item = make_review_item(
            cleaned_data={
                "title": "No Dates",
                "application_deadline": "",
                "program_start_date": None,
            }
        )
        scholarship = approve_review_item(item)
        self.assertIsNone(scholarship.application_deadline)
        self.assertIsNone(scholarship.program_start_date)


class OverridesTests(TestCase):
    def test_overrides_apply_on_top_of_cleaned_data(self):
        item = make_review_item(
            cleaned_data={
                "title": "Original",
                "provider": "Original Provider",
                "status": "open",
            }
        )
        scholarship = approve_review_item(
            item,
            overrides={"title": "Reviewer Edited", "status": "closed"},
        )
        self.assertEqual(scholarship.title, "Reviewer Edited")
        self.assertEqual(scholarship.provider, "Original Provider")
        self.assertEqual(scholarship.status, "closed")

    def test_overrides_with_invalid_key_ignored(self):
        item = make_review_item(cleaned_data={"title": "X"})
        scholarship = approve_review_item(
            item, overrides={"bogus_field": "nope"}
        )
        self.assertEqual(scholarship.title, "X")
        self.assertFalse(hasattr(scholarship, "bogus_field"))

    def test_overrides_can_set_date(self):
        item = make_review_item(cleaned_data={"title": "X"})
        scholarship = approve_review_item(
            item, overrides={"application_deadline": "2027-01-31"}
        )
        self.assertEqual(scholarship.application_deadline, date(2027, 1, 31))


class AdminActionTests(TestCase):
    def _make_admin(self):
        admin_instance = ReviewItemAdmin(ReviewItem, admin_site=Mock())
        admin_instance.message_user = Mock()
        return admin_instance

    def test_approve_selected_creates_scholarships(self):
        item = make_review_item()
        admin = self._make_admin()
        qs = ReviewItem.objects.filter(pk=item.pk)

        admin.approve_selected(Mock(), qs)

        self.assertEqual(Scholarship.objects.count(), 1)
        item.refresh_from_db()
        self.assertEqual(item.status, "approved")
        admin.message_user.assert_called()

    def test_approve_selected_reports_success_and_failure(self):
        good = make_review_item(source_url="https://example.com/good")
        bad = make_review_item(
            source_url="https://nope.example.com/missing",
            review_type="update",
            cleaned_data={"title": "Ghost"},
        )
        admin = self._make_admin()
        qs = ReviewItem.objects.all()

        admin.approve_selected(Mock(), qs)

        self.assertEqual(Scholarship.objects.count(), 1)
        good.refresh_from_db()
        bad.refresh_from_db()
        self.assertEqual(good.status, "approved")
        self.assertEqual(bad.status, "pending")
        self.assertGreaterEqual(admin.message_user.call_count, 2)

    def test_approve_selected_skips_non_pending(self):
        item = make_review_item()
        item.mark_approved()
        admin = self._make_admin()
        qs = ReviewItem.objects.filter(pk=item.pk)

        admin.approve_selected(Mock(), qs)

        self.assertEqual(Scholarship.objects.count(), 0)
        admin.message_user.assert_called_once()

    def test_approve_selected_no_pending_creates_nothing(self):
        admin = self._make_admin()
        admin.approve_selected(Mock(), ReviewItem.objects.none())
        self.assertEqual(Scholarship.objects.count(), 0)
