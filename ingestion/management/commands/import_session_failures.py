import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ingestion.models import PendingUrl


class Command(BaseCommand):
    help = (
        "Import failed extraction URLs from a session JSON file into PendingUrl. "
        "Each entry should have keys: url, failure_type, error, attempts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "session_file",
            type=str,
            help="Path to JSON file containing failed extraction entries",
        )

    def handle(self, *args, **options):
        session_path = Path(options["session_file"])

        if not session_path.exists():
            raise CommandError(f"File not found: {session_path}")

        try:
            with session_path.open() as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {session_path}: {exc}")

        if not isinstance(data, list):
            raise CommandError(f"Expected a JSON list, got {type(data).__name__}")

        if len(data) == 0:
            self.stdout.write(
                self.style.WARNING("Session file contains no entries. Nothing to import.")
            )
            return

        imported = 0
        for entry in data:
            if not isinstance(entry, dict):
                continue
            url = entry.get("url")
            if not url:
                continue
            PendingUrl.objects.update_or_create(
                url=url,
                defaults={
                    "source": "failed_extraction",
                    "failure_type": entry.get("failure_type"),
                    "attempts": entry.get("attempts", 0),
                    "last_error": entry.get("error"),
                    "processed": False,
                },
            )
            imported += 1

        self.stdout.write(
            self.style.SUCCESS(f"Imported {imported} session failures to PendingUrl")
        )
