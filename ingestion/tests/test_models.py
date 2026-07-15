from django.db.utils import IntegrityError
from django.test import TestCase
from django.utils import timezone

from ingestion.models import PendingUrl, ReviewItem


class ReviewItemModelTests(TestCase):
    def test_str_includes_review_type_url_status(self) -> None:
        item = ReviewItem.objects.create(
            source_url="https://example.com/scholarship",
            review_type="new",
            raw_extraction={"title": "Test"},
            cleaned_data={"title": "Test"},
        )
        result = str(item)
        self.assertIn("[new]", result)
        self.assertIn("https://example.com/scholarship", result)
        self.assertIn("pending", result)
        self.assertNotIn("(user)", result)

    def test_str_includes_user_flag_when_user_submitted(self) -> None:
        item = ReviewItem.objects.create(
            source_url="https://example.com/scholarship",
            review_type="new",
            is_user_submitted=True,
            raw_extraction={},
            cleaned_data={},
        )
        result = str(item)
        self.assertIn("(user)", result)

    def test_str_truncates_long_url(self) -> None:
        long_url = "https://example.com/" + "a" * 100
        item = ReviewItem.objects.create(
            source_url=long_url,
            review_type="new",
            raw_extraction={},
            cleaned_data={},
        )
        result = str(item)
        self.assertIn(long_url[:60], result)
        self.assertNotIn(long_url, result)

    def test_mark_approved_sets_status_and_reviewed_at(self) -> None:
        item = ReviewItem.objects.create(
            source_url="https://example.com/scholarship",
            review_type="new",
            raw_extraction={},
            cleaned_data={},
        )
        before = timezone.now()
        item.mark_approved()
        after = timezone.now()
        item.refresh_from_db()
        self.assertEqual(item.status, "approved")
        self.assertIsNotNone(item.reviewed_at)
        self.assertGreaterEqual(item.reviewed_at, before)
        self.assertLessEqual(item.reviewed_at, after)

    def test_mark_rejected_sets_status_and_reviewed_at(self) -> None:
        item = ReviewItem.objects.create(
            source_url="https://example.com/scholarship",
            review_type="new",
            raw_extraction={},
            cleaned_data={},
        )
        before = timezone.now()
        item.mark_rejected()
        after = timezone.now()
        item.refresh_from_db()
        self.assertEqual(item.status, "rejected")
        self.assertIsNotNone(item.reviewed_at)
        self.assertGreaterEqual(item.reviewed_at, before)
        self.assertLessEqual(item.reviewed_at, after)

    def test_default_status_is_pending(self) -> None:
        item = ReviewItem.objects.create(
            source_url="https://example.com/scholarship",
            review_type="new",
            raw_extraction={},
            cleaned_data={},
        )
        self.assertEqual(item.status, "pending")

    def test_default_is_user_submitted_is_false(self) -> None:
        item = ReviewItem.objects.create(
            source_url="https://example.com/scholarship",
            review_type="new",
            raw_extraction={},
            cleaned_data={},
        )
        self.assertFalse(item.is_user_submitted)

    def test_unique_together_constraint_on_duplicate_pending(self) -> None:
        ReviewItem.objects.create(
            source_url="https://example.com/scholarship",
            review_type="new",
            status="pending",
            raw_extraction={},
            cleaned_data={},
        )
        with self.assertRaises(IntegrityError):
            ReviewItem.objects.create(
                source_url="https://example.com/scholarship",
                review_type="new",
                status="pending",
                raw_extraction={},
                cleaned_data={},
            )

    def test_raw_extraction_and_cleaned_data_jsonfields_work(self) -> None:
        raw = {"title": "Test", "amount": 5000}
        cleaned = {"title": "Test", "amount": "$5,000"}
        item = ReviewItem.objects.create(
            source_url="https://example.com/scholarship",
            review_type="new",
            raw_extraction=raw,
            cleaned_data=cleaned,
        )
        item.refresh_from_db()
        self.assertEqual(item.raw_extraction, raw)
        self.assertEqual(item.cleaned_data, cleaned)

    def test_diffs_can_be_null(self) -> None:
        item = ReviewItem.objects.create(
            source_url="https://example.com/scholarship",
            review_type="new",
            raw_extraction={},
            cleaned_data={},
            diffs=None,
        )
        item.refresh_from_db()
        self.assertIsNone(item.diffs)


class PendingUrlModelTests(TestCase):
    def test_str_returns_user_submitted_url(self) -> None:
        pending = PendingUrl.objects.create(url="https://example.com/scholarship")
        self.assertEqual(
            str(pending), "[user] https://example.com/scholarship"
        )

    def test_url_must_be_unique(self) -> None:
        PendingUrl.objects.create(url="https://example.com/scholarship")
        with self.assertRaises(IntegrityError):
            PendingUrl.objects.create(url="https://example.com/scholarship")

    def test_default_processed_is_false(self) -> None:
        pending = PendingUrl.objects.create(url="https://example.com/scholarship")
        self.assertFalse(pending.processed)

    def test_meta_ordering(self) -> None:
        self.assertEqual(PendingUrl._meta.ordering, ["-submitted_at"])
