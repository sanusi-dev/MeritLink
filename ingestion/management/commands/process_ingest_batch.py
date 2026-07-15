import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ingestion.models import ReviewItem, PendingUrl
from ingestion.services.cleaning import clean_extracted_data
from ingestion.services.deduplication import find_existing_record


class Command(BaseCommand):
    help = (
        "Process a batch of extracted scholarship data (JSON) and create ReviewItems. "
        "Used by the local ingestion script."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "batch_file",
            type=str,
            help="Path to JSON file containing extracted items",
        )
        parser.add_argument(
            "--batch-id",
            type=str,
            default="",
            help="Optional identifier for this batch",
        )

    def handle(self, *args, **options):
        batch_path = Path(options["batch_file"])
        batch_id = options["batch_id"]

        if not batch_path.exists():
            raise CommandError(f"File not found: {batch_path}")

        with batch_path.open() as f:
            data = json.load(f)

        if not isinstance(data, list):
            data = data.get("items", data) if isinstance(data, dict) else []

        created = 0
        skipped = 0

        for item in data:
            url = item.get("source_url")
            if not url:
                self.stdout.write(self.style.WARNING("Skipping item with no URL"))
                skipped += 1
                continue

            # Run cleaning pipeline
            cleaned = clean_extracted_data(item)

            # Check if this looks like an update
            existing = find_existing_record(url)
            review_type = "update" if existing else "new"

            # Create ReviewItem (avoid duplicates in pending state)
            obj, created_flag = ReviewItem.objects.get_or_create(
                source_url=url,
                review_type=review_type,
                status="pending",
                defaults={
                    "raw_extraction": item,
                    "cleaned_data": cleaned,
                    "is_user_submitted": item.get("is_user_submitted", False),
                    "batch_id": batch_id,
                },
            )

            if created_flag:
                created += 1
                self.stdout.write(f"  Created ReviewItem for {url[:70]}")
            else:
                skipped += 1

            # Mark any matching PendingUrl as processed
            PendingUrl.objects.filter(url=url, processed=False).update(
                processed=True, processed_at=timezone.now()
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {len(data)} items → {created} new ReviewItems, {skipped} skipped"
            )
        )
