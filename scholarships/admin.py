from django.contrib import admin
from .models import Scholarship


@admin.register(Scholarship)
class ScholarshipAdmin(admin.ModelAdmin):
    list_display = ["title", "provider", "application_deadline", "status", "is_user_submitted"]
    list_filter = ["status", "is_user_submitted", "application_deadline"]
    search_fields = ["title", "provider", "source_url"]
    readonly_fields = ["source_url", "last_verified", "created_at", "updated_at"]

    fieldsets = (
        ("Basic", {
            "fields": ("title", "provider", "source_url", "application_url")
        }),
        ("Dates & Status", {
            "fields": ("application_deadline", "program_start_date", "status")
        }),
        ("Eligibility (Core)", {
            "fields": (
                "eligible_nationalities", "eligible_study_levels", "min_gpa",
                "gpa_scale", "eligible_fields_of_study", "study_destinations"
            )
        }),
        ("Funding", {
            "fields": ("funding_details", "funding_amount_approx")
        }),
        ("Other", {
            "fields": ("description", "short_summary", "tags", "is_user_submitted")
        }),
    )

