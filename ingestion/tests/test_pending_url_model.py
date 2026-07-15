from django.test import TestCase

from ingestion.models import PendingUrl


class PendingUrlNewFieldsTests(TestCase):
    """Test PendingUrl model fields: source, failure_type, attempts, last_error."""

    def test_default_source_is_user(self) -> None:
        pending = PendingUrl.objects.create(url="https://example.com/default-source")
        self.assertEqual(pending.source, "user")

    def test_default_attempts_is_zero(self) -> None:
        pending = PendingUrl.objects.create(url="https://example.com/default-attempts")
        self.assertEqual(pending.attempts, 0)

    def test_failure_type_is_nullable(self) -> None:
        pending = PendingUrl.objects.create(url="https://example.com/null-failure-type")
        self.assertIsNone(pending.failure_type)

    def test_last_error_is_nullable(self) -> None:
        pending = PendingUrl.objects.create(url="https://example.com/null-last-error")
        self.assertIsNone(pending.last_error)

    def test_str_returns_source_and_url_format(self) -> None:
        pending = PendingUrl.objects.create(
            url="https://example.com/str-test", source="failed_extraction"
        )
        self.assertEqual(str(pending), "[failed_extraction] https://example.com/str-test")

    def test_create_with_source_failed_extraction(self) -> None:
        pending = PendingUrl.objects.create(
            url="https://example.com/failed-src", source="failed_extraction"
        )
        self.assertEqual(pending.source, "failed_extraction")

    def test_create_with_all_failure_fields_populated(self) -> None:
        pending = PendingUrl.objects.create(
            url="https://example.com/all-fields",
            source="failed_extraction",
            failure_type="timeout",
            attempts=3,
            last_error="Connection timed out after 30s",
        )
        pending.refresh_from_db()
        self.assertEqual(pending.source, "failed_extraction")
        self.assertEqual(pending.failure_type, "timeout")
        self.assertEqual(pending.attempts, 3)
        self.assertEqual(pending.last_error, "Connection timed out after 30s")
