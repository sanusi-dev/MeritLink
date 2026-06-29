from django.db import models
from django.utils import timezone


class PendingUrl(models.Model):
    """
    URLs submitted by users via the public form.
    These are picked up by the ingestion script and processed.
    """
    url = models.URLField(unique=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"User submitted: {self.url}"


class ReviewItem(models.Model):
    """
    Staging item for both new scholarships and updates to existing ones.
    Created by the ingestion script (via management command or API).
    """
    REVIEW_TYPE_CHOICES = [
        ("new", "New Scholarship"),
        ("update", "Update to Existing"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    source_url = models.URLField(db_index=True)
    review_type = models.CharField(max_length=10, choices=REVIEW_TYPE_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")

    # Raw vs cleaned data from the LLM + cleaning pipeline
    raw_extraction = models.JSONField()
    cleaned_data = models.JSONField()

    # Only relevant for updates
    diffs = models.JSONField(null=True, blank=True)

    # Tracking
    is_user_submitted = models.BooleanField(default=False)
    batch_id = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # Future: reviewed_by = models.ForeignKey(User...)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("source_url", "review_type", "status")]  # prevent duplicates in pending

    def __str__(self):
        flag = " (user)" if self.is_user_submitted else ""
        return f"[{self.review_type}] {self.source_url[:60]}{flag} - {self.status}"

    def mark_approved(self):
        self.status = "approved"
        self.reviewed_at = timezone.now()
        self.save()

    def mark_rejected(self):
        self.status = "rejected"
        self.reviewed_at = timezone.now()
        self.save()
