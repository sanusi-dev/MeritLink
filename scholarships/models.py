from django.db import models
from django.utils import timezone


class Scholarship(models.Model):
    """
    The canonical, clean, usable scholarship record.
    This is the live data that powers matching, dashboards, tracker, etc.
    Once accepted through the ingestion pipeline, this is considered
    fully cleaned and genuine.
    """

    # --- Basic Info (mostly core) ---
    title = models.CharField(max_length=255)
    provider = models.CharField(max_length=255, blank=True)
    source_url = models.URLField(unique=True, help_text="Original page we scraped from")
    application_url = models.URLField(blank=True, help_text="Direct apply link if different")

    description = models.TextField(blank=True)
    short_summary = models.TextField(blank=True)

    # --- Key Dates & Status (core + important) ---
    application_deadline = models.DateField(null=True, blank=True)
    program_start_date = models.DateField(null=True, blank=True)

    STATUS_CHOICES = [
        ("open", "Open"),
        ("closed", "Closed"),
        ("results_out", "Results Announced"),
        ("unknown", "Unknown"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")

    # --- Eligibility - Hard Gates (core for matching) ---
    # Store as JSON for flexibility (list of countries or special values)
    eligible_nationalities = models.JSONField(
        default=list, blank=True,
        help_text="List of eligible countries or ['all']"
    )
    eligible_study_levels = models.JSONField(
        default=list, blank=True,
        help_text="e.g. ['Bachelors', 'Masters', 'PhD']"
    )
    min_gpa = models.FloatField(null=True, blank=True)
    gpa_scale = models.CharField(max_length=20, blank=True, help_text="e.g. 4.0, 5.0")

    eligible_fields_of_study = models.JSONField(
        default=list, blank=True,
        help_text="List of fields or ['any']"
    )

    # Other demographics (forgivable for now)
    age_limit_max = models.PositiveIntegerField(null=True, blank=True)
    financial_need_required = models.BooleanField(default=False)

    # --- Study & Funding (core) ---
    study_destinations = models.JSONField(
        default=list, blank=True,
        help_text="Countries where you can use the scholarship"
    )

    funding_details = models.TextField(
        blank=True,
        help_text="What is covered (tuition, stipend, travel...)"
    )
    funding_amount_approx = models.JSONField(
        default=dict, blank=True,
        help_text="Structured amount info if available"
    )
    number_of_awards = models.PositiveIntegerField(null=True, blank=True)

    # --- Requirements & Benefits (mostly forgivable) ---
    eligibility_details = models.TextField(blank=True)
    required_documents = models.TextField(blank=True)
    selection_criteria = models.TextField(blank=True)
    benefits = models.TextField(blank=True)
    notes_for_applicants = models.TextField(blank=True)

    tags = models.JSONField(default=list, blank=True)

    # --- Tracking ---
    is_user_submitted = models.BooleanField(
        default=False,
        help_text="Came through public user submission form"
    )
    last_verified = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Scholarships"
        ordering = ["-application_deadline", "title"]

    def __str__(self):
        return self.title

    def is_open(self):
        if not self.application_deadline:
            return True
        return self.application_deadline >= timezone.now().date()
