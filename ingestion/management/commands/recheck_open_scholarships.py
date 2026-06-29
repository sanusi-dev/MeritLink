from django.core.management.base import BaseCommand
from django.utils import timezone

from scholarships.models import Scholarship
from ingestion.models import ReviewItem
from ingestion.services.cleaning import clean_extracted_data


class Command(BaseCommand):
    help = (
        "Trigger re-checks for live scholarships with future deadlines. "
        "In a real run the external script would do the heavy lifting. "
        "This command is useful for local testing or manual re-queues."
    )

    def handle(self, *args, **options):
        today = timezone.now().date()
        to_recheck = Scholarship.objects.filter(
            application_deadline__gte=today,
            source_url__isnull=False,
        )

        queued = 0
        for scholarship in to_recheck:
            # In real life the external script would re-fetch + re-extract.
            # Here we just create a lightweight update ReviewItem as a signal.
            ReviewItem.objects.get_or_create(
                source_url=scholarship.source_url,
                review_type="update",
                status="pending",
                defaults={
                    "raw_extraction": {"note": "recheck requested"},
                    "cleaned_data": clean_extracted_data({}),
                    "diffs": {},
                    "is_user_submitted": scholarship.is_user_submitted,
                },
            )
            queued += 1

        self.stdout.write(
            self.style.SUCCESS(f"Queued {queued} update review items for re-check")
        )
