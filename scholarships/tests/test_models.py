from datetime import timedelta

from django.db.utils import IntegrityError
from django.test import TestCase
from django.utils import timezone

from scholarships.models import Scholarship


class ScholarshipModelTests(TestCase):
    def test_str_returns_title(self) -> None:
        scholarship = Scholarship.objects.create(
            title="Test Scholarship",
            source_url="https://example.com/scholarship",
        )
        self.assertEqual(str(scholarship), "Test Scholarship")

    def test_is_open_returns_true_when_deadline_is_none(self) -> None:
        scholarship = Scholarship.objects.create(
            title="Test Scholarship",
            source_url="https://example.com/scholarship",
        )
        self.assertTrue(scholarship.is_open())

    def test_is_open_returns_true_when_deadline_in_future(self) -> None:
        future_date = timezone.now().date() + timedelta(days=30)
        scholarship = Scholarship.objects.create(
            title="Test Scholarship",
            source_url="https://example.com/scholarship",
            application_deadline=future_date,
        )
        self.assertTrue(scholarship.is_open())

    def test_is_open_returns_false_when_deadline_in_past(self) -> None:
        past_date = timezone.now().date() - timedelta(days=30)
        scholarship = Scholarship.objects.create(
            title="Test Scholarship",
            source_url="https://example.com/scholarship",
            application_deadline=past_date,
        )
        self.assertFalse(scholarship.is_open())

    def test_default_status_is_open(self) -> None:
        scholarship = Scholarship.objects.create(
            title="Test Scholarship",
            source_url="https://example.com/scholarship",
        )
        self.assertEqual(scholarship.status, "open")

    def test_default_eligible_nationalities_is_empty_list(self) -> None:
        scholarship = Scholarship.objects.create(
            title="Test Scholarship",
            source_url="https://example.com/scholarship",
        )
        self.assertEqual(scholarship.eligible_nationalities, [])

    def test_source_url_must_be_unique(self) -> None:
        Scholarship.objects.create(
            title="First Scholarship",
            source_url="https://example.com/scholarship",
        )
        with self.assertRaises(IntegrityError):
            Scholarship.objects.create(
                title="Second Scholarship",
                source_url="https://example.com/scholarship",
            )

    def test_last_verified_defaults_to_now(self) -> None:
        before = timezone.now()
        scholarship = Scholarship.objects.create(
            title="Test Scholarship",
            source_url="https://example.com/scholarship",
        )
        after = timezone.now()
        self.assertIsNotNone(scholarship.last_verified)
        self.assertGreaterEqual(scholarship.last_verified, before)
        self.assertLessEqual(scholarship.last_verified, after)

    def test_created_at_set_automatically(self) -> None:
        before = timezone.now()
        scholarship = Scholarship.objects.create(
            title="Test Scholarship",
            source_url="https://example.com/scholarship",
        )
        after = timezone.now()
        self.assertIsNotNone(scholarship.created_at)
        self.assertGreaterEqual(scholarship.created_at, before)
        self.assertLessEqual(scholarship.created_at, after)

    def test_updated_at_set_automatically(self) -> None:
        before = timezone.now()
        scholarship = Scholarship.objects.create(
            title="Test Scholarship",
            source_url="https://example.com/scholarship",
        )
        after = timezone.now()
        self.assertIsNotNone(scholarship.updated_at)
        self.assertGreaterEqual(scholarship.updated_at, before)
        self.assertLessEqual(scholarship.updated_at, after)

    def test_meta_ordering(self) -> None:
        self.assertEqual(
            Scholarship._meta.ordering, ["-application_deadline", "title"]
        )

    def test_json_field_defaults(self) -> None:
        scholarship = Scholarship.objects.create(
            title="Test Scholarship",
            source_url="https://example.com/scholarship",
        )
        self.assertEqual(scholarship.eligible_study_levels, [])
        self.assertEqual(scholarship.eligible_fields_of_study, [])
        self.assertEqual(scholarship.study_destinations, [])
        self.assertEqual(scholarship.funding_amount_approx, {})
        self.assertEqual(scholarship.tags, [])
