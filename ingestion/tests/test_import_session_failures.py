import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from ingestion.models import PendingUrl


class ImportSessionFailuresCommandTests(TestCase):
    """Test the import_session_failures management command."""

    def _write_json(self, directory: str, data) -> str:
        path = Path(directory) / "session.json"
        with path.open("w") as f:
            json.dump(data, f)
        return str(path)

    def test_valid_json_creates_pending_urls(self) -> None:
        failures = [
            {
                "url": "https://example.com/f1",
                "failure_type": "timeout",
                "error": "Connection timed out",
                "attempts": 2,
            },
            {
                "url": "https://example.com/f2",
                "failure_type": "parse_error",
                "error": "Invalid JSON response",
                "attempts": 1,
            },
            {
                "url": "https://example.com/f3",
                "failure_type": "http_error",
                "error": "Server returned 500",
                "attempts": 3,
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_json(tmpdir, failures)
            out = StringIO()
            call_command("import_session_failures", path, stdout=out)

        self.assertEqual(PendingUrl.objects.count(), 3)
        for entry in failures:
            pending = PendingUrl.objects.get(url=entry["url"])
            self.assertEqual(pending.source, "failed_extraction")
            self.assertEqual(pending.failure_type, entry["failure_type"])
            self.assertEqual(pending.attempts, entry["attempts"])
            self.assertEqual(pending.last_error, entry["error"])
            self.assertFalse(pending.processed)
        self.assertIn("Imported 3", out.getvalue())

    def test_updates_existing_pending_url_failure_fields(self) -> None:
        pending = PendingUrl.objects.create(
            url="https://example.com/existing",
            source="failed_extraction",
            failure_type="old_type",
            attempts=1,
            last_error="old error",
        )
        failures = [
            {
                "url": "https://example.com/existing",
                "failure_type": "new_type",
                "error": "new error",
                "attempts": 5,
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_json(tmpdir, failures)
            call_command("import_session_failures", path, stdout=StringIO())

        self.assertEqual(PendingUrl.objects.count(), 1)
        pending.refresh_from_db()
        self.assertEqual(pending.failure_type, "new_type")
        self.assertEqual(pending.attempts, 5)
        self.assertEqual(pending.last_error, "new error")
        self.assertEqual(pending.source, "failed_extraction")

    def test_overwrites_user_source_to_failed_extraction(self) -> None:
        PendingUrl.objects.create(
            url="https://example.com/user-url",
            source="user",
        )
        failures = [
            {
                "url": "https://example.com/user-url",
                "failure_type": "timeout",
                "error": "timed out",
                "attempts": 2,
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_json(tmpdir, failures)
            call_command("import_session_failures", path, stdout=StringIO())

        pending = PendingUrl.objects.get(url="https://example.com/user-url")
        self.assertEqual(pending.source, "failed_extraction")
        self.assertEqual(pending.failure_type, "timeout")
        self.assertEqual(pending.attempts, 2)
        self.assertEqual(pending.last_error, "timed out")

    def test_empty_json_list_prints_warning_and_creates_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_json(tmpdir, [])
            out = StringIO()
            call_command("import_session_failures", path, stdout=out)

        self.assertEqual(PendingUrl.objects.count(), 0)
        self.assertIn("Nothing to import", out.getvalue())

    def test_file_not_found_raises_command_error(self) -> None:
        with self.assertRaises(CommandError):
            call_command(
                "import_session_failures",
                "/nonexistent/path/to/session.json",
                stdout=StringIO(),
            )

    def test_invalid_json_raises_command_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.json"
            with path.open("w") as f:
                f.write("{invalid json content")
            with self.assertRaises(CommandError):
                call_command("import_session_failures", str(path), stdout=StringIO())

    def test_malformed_entries_skipped_gracefully(self) -> None:
        failures = [
            {"url": "https://example.com/valid", "failure_type": "fetch", "error": "timeout", "attempts": 1},
            {"failure_type": "fetch", "error": "no url key"},
            "not a dict",
            {"url": "", "failure_type": "fetch", "error": "empty url"},
            {"url": "https://example.com/also-valid", "failure_type": "extraction", "error": "bad parse", "attempts": 2},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._write_json(tmpdir, failures)
            out = StringIO()
            call_command("import_session_failures", path, stdout=out)

        self.assertEqual(PendingUrl.objects.count(), 2)
        self.assertTrue(PendingUrl.objects.filter(url="https://example.com/valid").exists())
        self.assertTrue(PendingUrl.objects.filter(url="https://example.com/also-valid").exists())
        self.assertIn("Imported 2", out.getvalue())
