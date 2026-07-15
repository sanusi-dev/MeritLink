import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

from django.conf import settings
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from scholarships.admin import ScholarshipAdmin
from scholarships.models import Scholarship

User = get_user_model()

CREATE_TABLE_SQL = """CREATE TABLE IF NOT EXISTS crawled_urls (
    url TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    last_checked TEXT NOT NULL,
    known_deadline TEXT,
    status TEXT,
    source TEXT,
    user_submitted INTEGER DEFAULT 0,
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    failure_type TEXT
)"""


class QueueSelectedForRecheckActionTests(TestCase):
    """Test the queue_selected_for_recheck admin action on ScholarshipAdmin."""

    def setUp(self) -> None:
        self.db_path = Path(settings.BASE_DIR) / "scripts" / "crawl_state.db"
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
        conn.close()

        self.site = AdminSite()
        self.factory = RequestFactory()
        self.admin = ScholarshipAdmin(Scholarship, self.site)
        self.user = User.objects.create_user(
            username="admin", password="testpass123", is_staff=True
        )

    def tearDown(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("DELETE FROM crawled_urls")
        conn.commit()
        conn.close()

    def _make_request(self):
        request = self.factory.post("/admin/scholarships/scholarship/")
        request.user = self.user
        request._messages = MagicMock()
        return request

    def test_queue_selected_for_recheck_writes_urls_to_crawl_state_db(self) -> None:
        s1 = Scholarship.objects.create(
            title="Scholarship 1", source_url="https://example.com/recheck-1"
        )
        s2 = Scholarship.objects.create(
            title="Scholarship 2", source_url="https://example.com/recheck-2"
        )

        request = self._make_request()
        queryset = Scholarship.objects.filter(pk__in=[s1.pk, s2.pk])
        self.admin.queue_selected_for_recheck(request, queryset)

        conn = sqlite3.connect(str(self.db_path))
        rows = conn.execute(
            "SELECT url, source, status FROM crawled_urls ORDER BY url"
        ).fetchall()
        conn.close()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], "https://example.com/recheck-1")
        self.assertEqual(rows[0][1], "manual_recheck")
        self.assertEqual(rows[0][2], "discovered")
        self.assertEqual(rows[1][0], "https://example.com/recheck-2")
        self.assertEqual(rows[1][1], "manual_recheck")
        self.assertEqual(rows[1][2], "discovered")


class QueueRecheckViewTests(TestCase):
    """Test the queue_recheck view for a single scholarship."""

    def setUp(self) -> None:
        self.db_path = Path(settings.BASE_DIR) / "scripts" / "crawl_state.db"
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
        conn.close()

        self.user = User.objects.create_user(
            username="admin", password="testpass123", is_staff=True
        )

    def tearDown(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("DELETE FROM crawled_urls")
        conn.commit()
        conn.close()

    def test_queue_recheck_writes_url_and_redirects(self) -> None:
        scholarship = Scholarship.objects.create(
            title="Recheck Test Scholarship",
            source_url="https://example.com/queue-recheck-test",
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("scholarships:queue_recheck", args=[scholarship.pk])
        )
        self.assertEqual(response.status_code, 302)

        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute(
            "SELECT url, source, status FROM crawled_urls WHERE url = ?",
            ("https://example.com/queue-recheck-test",),
        ).fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "https://example.com/queue-recheck-test")
        self.assertEqual(row[1], "manual_recheck")
        self.assertEqual(row[2], "discovered")
