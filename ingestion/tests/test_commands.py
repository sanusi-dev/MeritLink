import json
import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from ingestion.models import PendingUrl, ReviewItem
from scholarships.models import Scholarship


class ProcessIngestBatchCommandTests(TestCase):
    def _write_batch_file(self, directory: str, data) -> str:
        path = Path(directory) / "batch.json"
        with path.open("w") as f:
            json.dump(data, f)
        return str(path)

    def test_processes_valid_json_creates_review_items(self):
        items = [
            {
                "source_url": "https://example.com/schol1",
                "title": "Scholarship One",
                "is_user_submitted": True,
            },
            {
                "source_url": "https://example.com/schol2",
                "title": "Scholarship Two",
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_batch_file(tmpdir, items)
            out = StringIO()
            call_command("process_ingest_batch", path, stdout=out)

        self.assertEqual(ReviewItem.objects.count(), 2)
        item1 = ReviewItem.objects.get(source_url="https://example.com/schol1")
        self.assertEqual(item1.review_type, "new")
        self.assertEqual(item1.status, "pending")
        self.assertEqual(item1.raw_extraction["title"], "Scholarship One")
        self.assertTrue(item1.is_user_submitted)
        item2 = ReviewItem.objects.get(source_url="https://example.com/schol2")
        self.assertEqual(item2.review_type, "new")
        self.assertFalse(item2.is_user_submitted)
        self.assertIn("Processed 2 items", out.getvalue())
        self.assertIn("2 new ReviewItems", out.getvalue())

    def test_skips_items_with_no_source_url(self):
        items = [{"title": "No URL Scholarship"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_batch_file(tmpdir, items)
            out = StringIO()
            call_command("process_ingest_batch", path, stdout=out)

        self.assertEqual(ReviewItem.objects.count(), 0)
        self.assertIn("Skipping item with no URL", out.getvalue())
        self.assertIn("0 new ReviewItems", out.getvalue())
        self.assertIn("1 skipped", out.getvalue())

    def test_runs_cleaning_pipeline_normalizes_data(self):
        items = [
            {
                "source_url": "https://example.com/schol1",
                "application_deadline": "  2025-12-31  ",
                "eligible_nationalities": "US, UK",
                "description": "  This is   a  test  apply now  ",
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_batch_file(tmpdir, items)
            call_command("process_ingest_batch", path, stdout=StringIO())

        item = ReviewItem.objects.get(source_url="https://example.com/schol1")
        self.assertEqual(item.cleaned_data["application_deadline"], "2025-12-31")
        self.assertEqual(item.cleaned_data["eligible_nationalities"], ["United States", "United Kingdom"])
        self.assertEqual(item.cleaned_data["description"], "This is a test")
        self.assertEqual(item.cleaned_data["status"], "open")
        self.assertEqual(item.cleaned_data["extraction_confidence"], 0.2)
        self.assertEqual(
            item.raw_extraction["application_deadline"], "  2025-12-31  "
        )

    def test_creates_new_review_item_when_url_not_in_live_db(self):
        items = [{"source_url": "https://example.com/new-schol", "title": "New"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_batch_file(tmpdir, items)
            call_command("process_ingest_batch", path, stdout=StringIO())

        item = ReviewItem.objects.get(source_url="https://example.com/new-schol")
        self.assertEqual(item.review_type, "new")

    def test_creates_update_review_item_when_url_exists_in_db(self):
        Scholarship.objects.create(
            title="Existing",
            source_url="https://example.com/existing",
        )
        items = [{"source_url": "https://example.com/existing", "title": "Updated"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_batch_file(tmpdir, items)
            call_command("process_ingest_batch", path, stdout=StringIO())

        item = ReviewItem.objects.get(source_url="https://example.com/existing")
        self.assertEqual(item.review_type, "update")

    def test_does_not_create_duplicate_pending_review_items(self):
        items = [{"source_url": "https://example.com/dup", "title": "Dup"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_batch_file(tmpdir, items)
            call_command("process_ingest_batch", path, stdout=StringIO())
            call_command("process_ingest_batch", path, stdout=StringIO())

        self.assertEqual(ReviewItem.objects.count(), 1)

    def test_marks_matching_pending_url_as_processed(self):
        pending = PendingUrl.objects.create(url="https://example.com/pending")
        items = [{"source_url": "https://example.com/pending", "title": "Test"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_batch_file(tmpdir, items)
            call_command("process_ingest_batch", path, stdout=StringIO())

        pending.refresh_from_db()
        self.assertTrue(pending.processed)
        self.assertIsNotNone(pending.processed_at)

    def test_handles_json_with_items_key(self):
        data = {
            "items": [
                {"source_url": "https://example.com/items-1", "title": "A"},
                {"source_url": "https://example.com/items-2", "title": "B"},
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_batch_file(tmpdir, data)
            out = StringIO()
            call_command("process_ingest_batch", path, stdout=out)

        self.assertEqual(ReviewItem.objects.count(), 2)
        self.assertIn("Processed 2 items", out.getvalue())

    def test_handles_json_that_is_directly_a_list(self):
        items = [{"source_url": "https://example.com/list-1", "title": "A"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_batch_file(tmpdir, items)
            out = StringIO()
            call_command("process_ingest_batch", path, stdout=out)

        self.assertEqual(ReviewItem.objects.count(), 1)
        self.assertIn("Processed 1 items", out.getvalue())

    def test_raises_command_error_when_file_not_found(self):
        with self.assertRaises(CommandError):
            call_command("process_ingest_batch", "/nonexistent/path.json")

    def test_uses_batch_id_option(self):
        items = [{"source_url": "https://example.com/batch-test", "title": "Test"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_batch_file(tmpdir, items)
            call_command(
                "process_ingest_batch",
                path,
                batch_id="test-batch-123",
                stdout=StringIO(),
            )

        item = ReviewItem.objects.get(source_url="https://example.com/batch-test")
        self.assertEqual(item.batch_id, "test-batch-123")


class RecheckOpenScholarshipsCommandTests(TestCase):
    def test_queues_update_review_items_for_future_deadlines(self):
        future_date = timezone.now().date() + timedelta(days=30)
        Scholarship.objects.create(
            title="Future Scholarship",
            source_url="https://example.com/future",
            application_deadline=future_date,
        )
        out = StringIO()
        call_command("recheck_open_scholarships", stdout=out)

        item = ReviewItem.objects.get(source_url="https://example.com/future")
        self.assertEqual(item.review_type, "update")
        self.assertEqual(item.status, "pending")
        self.assertIn("Queued 1", out.getvalue())

    def test_does_not_queue_for_past_deadlines(self):
        past_date = timezone.now().date() - timedelta(days=30)
        Scholarship.objects.create(
            title="Past Scholarship",
            source_url="https://example.com/past",
            application_deadline=past_date,
        )
        call_command("recheck_open_scholarships", stdout=StringIO())

        self.assertEqual(ReviewItem.objects.count(), 0)

    def test_does_not_queue_for_null_deadline(self):
        Scholarship.objects.create(
            title="No Deadline Scholarship",
            source_url="https://example.com/no-deadline",
            application_deadline=None,
        )
        call_command("recheck_open_scholarships", stdout=StringIO())

        self.assertEqual(ReviewItem.objects.count(), 0)

    def test_does_not_create_duplicate_pending_review_items(self):
        future_date = timezone.now().date() + timedelta(days=30)
        Scholarship.objects.create(
            title="Future",
            source_url="https://example.com/dup-recheck",
            application_deadline=future_date,
        )
        call_command("recheck_open_scholarships", stdout=StringIO())
        call_command("recheck_open_scholarships", stdout=StringIO())

        self.assertEqual(ReviewItem.objects.count(), 1)

    def test_sets_is_user_submitted_from_scholarship(self):
        future_date = timezone.now().date() + timedelta(days=30)
        Scholarship.objects.create(
            title="User Submitted",
            source_url="https://example.com/user-sub",
            application_deadline=future_date,
            is_user_submitted=True,
        )
        call_command("recheck_open_scholarships", stdout=StringIO())

        item = ReviewItem.objects.get(source_url="https://example.com/user-sub")
        self.assertTrue(item.is_user_submitted)

    def test_outputs_correct_count_message(self):
        future_date = timezone.now().date() + timedelta(days=30)
        for i in range(3):
            Scholarship.objects.create(
                title=f"Scholarship {i}",
                source_url=f"https://example.com/count-{i}",
                application_deadline=future_date,
            )
        out = StringIO()
        call_command("recheck_open_scholarships", stdout=out)

        self.assertIn("Queued 3 update review items for re-check", out.getvalue())
