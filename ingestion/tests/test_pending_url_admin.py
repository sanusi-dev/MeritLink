import json
from pathlib import Path
from unittest.mock import MagicMock

from django.conf import settings
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from ingestion.admin import PendingUrlAdmin
from ingestion.models import PendingUrl

User = get_user_model()


class ExportSelectedToJsonActionTests(TestCase):
    """Test the export_selected_to_json admin action on PendingUrlAdmin."""

    def setUp(self) -> None:
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.admin = PendingUrlAdmin(PendingUrl, self.site)
        self.user = User.objects.create_user(
            username="admin", password="testpass123", is_staff=True
        )
        self.export_path = Path(settings.BASE_DIR) / "exports" / "requeued_urls.json"

    def tearDown(self) -> None:
        if self.export_path.exists():
            self.export_path.unlink()

    def _make_request(self):
        request = self.factory.post("/admin/ingestion/pendingurl/")
        request.user = self.user
        request._messages = MagicMock()
        return request

    def test_export_writes_json_file(self) -> None:
        PendingUrl.objects.create(url="https://example.com/export-1")
        PendingUrl.objects.create(url="https://example.com/export-2")

        request = self._make_request()
        queryset = PendingUrl.objects.all()
        self.admin.export_selected_to_json(request, queryset)

        self.assertTrue(self.export_path.exists())
        with self.export_path.open() as f:
            data = json.load(f)
        self.assertEqual(len(data), 2)
        urls = [entry["url"] for entry in data]
        self.assertIn("https://example.com/export-1", urls)
        self.assertIn("https://example.com/export-2", urls)

    def test_exported_json_contains_url_and_user_submitted_true(self) -> None:
        PendingUrl.objects.create(url="https://example.com/spec-test")

        request = self._make_request()
        queryset = PendingUrl.objects.all()
        self.admin.export_selected_to_json(request, queryset)

        with self.export_path.open() as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["url"], "https://example.com/spec-test")
        self.assertTrue(data[0]["user_submitted"])

    def test_exported_pending_urls_marked_processed(self) -> None:
        p1 = PendingUrl.objects.create(url="https://example.com/proc-1")
        p2 = PendingUrl.objects.create(url="https://example.com/proc-2")

        request = self._make_request()
        queryset = PendingUrl.objects.all()
        self.admin.export_selected_to_json(request, queryset)

        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertTrue(p1.processed)
        self.assertIsNotNone(p1.processed_at)
        self.assertTrue(p2.processed)
        self.assertIsNotNone(p2.processed_at)

    def test_non_exported_pending_urls_remain_unprocessed(self) -> None:
        exported = PendingUrl.objects.create(url="https://example.com/will-export")
        non_exported = PendingUrl.objects.create(url="https://example.com/will-not-export")

        request = self._make_request()
        queryset = PendingUrl.objects.filter(url="https://example.com/will-export")
        self.admin.export_selected_to_json(request, queryset)

        exported.refresh_from_db()
        non_exported.refresh_from_db()
        self.assertTrue(exported.processed)
        self.assertFalse(non_exported.processed)
        self.assertIsNone(non_exported.processed_at)
