from django.contrib import admin
from .models import Scholarship


@admin.register(Scholarship)
class ScholarshipAdmin(admin.ModelAdmin):
    list_display = ["title", "provider", "application_deadline", "status", "is_user_submitted"]
    list_filter = ["status", "is_user_submitted", "application_deadline"]
    search_fields = ["title", "provider", "source_url"]
    readonly_fields = ["source_url", "last_verified", "created_at", "updated_at"]
    actions = ["queue_selected_for_recheck"]

    def queue_selected_for_recheck(self, request, queryset):
        import sqlite3
        from datetime import date
        from pathlib import Path
        from django.conf import settings

        db_path = Path(settings.BASE_DIR) / "scripts" / "crawl_state.db"
        today = date.today().isoformat()
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crawled_urls (
                url TEXT PRIMARY KEY,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                last_checked TEXT NOT NULL,
                known_deadline TEXT,
                status TEXT,
                failure_type TEXT,
                attempts INTEGER DEFAULT 0,
                last_error TEXT,
                source TEXT,
                user_submitted INTEGER DEFAULT 0
            )
        """)
        count = 0
        for scholarship in queryset:
            deadline = scholarship.application_deadline.isoformat() if scholarship.application_deadline else None
            conn.execute("""
                INSERT INTO crawled_urls (url, first_seen, last_seen, last_checked,
                                          known_deadline, status, source, user_submitted,
                                          attempts, last_error)
                VALUES (?, ?, ?, ?, ?, 'discovered', 'manual_recheck', 1, 0, NULL)
                ON CONFLICT(url) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    status = 'discovered',
                    attempts = 0,
                    last_error = NULL
            """, (scholarship.source_url, today, today, today, deadline))
            count += 1
        conn.commit()
        conn.close()
        self.message_user(request, f"Queued {count} scholarships for recheck. Click 'Run Queue' on the review page to process.")
    queue_selected_for_recheck.short_description = "Queue selected for recheck"

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

