import json
from pathlib import Path

from django.conf import settings
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from scholarships.models import Scholarship
from .models import PendingUrl, ReviewItem
from .services.approval import approve_review_item


@admin.register(PendingUrl)
class PendingUrlAdmin(admin.ModelAdmin):
    list_display = ["url", "source", "failure_type", "attempts", "last_error_truncated", "submitted_at", "processed"]
    list_filter = ["source", "failure_type", "processed"]
    search_fields = ["url"]
    readonly_fields = ["submitted_at"]
    actions = ["mark_as_unprocessed", "export_selected_to_json"]

    def last_error_truncated(self, obj):
        if obj.last_error and len(obj.last_error) > 80:
            return obj.last_error[:80] + "..."
        return obj.last_error
    last_error_truncated.short_description = "Error"

    def mark_as_unprocessed(self, request, queryset):
        queryset.update(processed=False)
    mark_as_unprocessed.short_description = "Mark selected as unprocessed"

    def export_selected_to_json(self, request, queryset):
        export_dir = Path(settings.BASE_DIR) / "exports"
        export_dir.mkdir(exist_ok=True)
        export_path = export_dir / "requeued_urls.json"

        urls = [{"url": obj.url, "user_submitted": True} for obj in queryset]
        with export_path.open("w") as f:
            json.dump(urls, f, indent=2)

        queryset.update(processed=True, processed_at=timezone.now())
        self.message_user(request, f"Exported {len(urls)} URLs to exports/requeued_urls.json")
    export_selected_to_json.short_description = "Export selected URLs to JSON for re-queue"


@admin.register(ReviewItem)
class ReviewItemAdmin(admin.ModelAdmin):
    list_display = [
        "short_url", "review_type", "status", "is_user_submitted",
        "created_at", "has_diffs"
    ]
    list_filter = ["review_type", "status", "is_user_submitted"]
    search_fields = ["source_url"]
    readonly_fields = ["source_url", "raw_extraction", "cleaned_data", "diffs", "created_at"]

    fieldsets = (
        (None, {
            "fields": ("source_url", "review_type", "status", "is_user_submitted")
        }),
        ("Data", {
            "fields": ("cleaned_data", "raw_extraction", "diffs")
        }),
        ("Metadata", {
            "fields": ("batch_id", "created_at", "reviewed_at")
        }),
    )

    actions = ["approve_selected", "reject_selected"]

    def short_url(self, obj):
        return obj.source_url[:80] + "..." if len(obj.source_url) > 80 else obj.source_url
    short_url.short_description = "URL"

    def has_diffs(self, obj):
        return bool(obj.diffs)
    has_diffs.boolean = True

    def approve_selected(self, request, queryset):
        pending = queryset.filter(status="pending")
        succeeded = 0
        failed = 0
        for item in pending:
            try:
                approve_review_item(item)
                succeeded += 1
            except (ValueError, Scholarship.DoesNotExist) as exc:
                failed += 1
                self.message_user(
                    request,
                    f"Failed to approve {item.source_url}: {exc}",
                    level=messages.ERROR,
                )
        self.message_user(
            request,
            f"Approved {succeeded} item(s), {failed} failed.",
        )
    approve_selected.short_description = "Approve selected (create/update Scholarship)"

    def reject_selected(self, request, queryset):
        for item in queryset.filter(status="pending"):
            item.mark_rejected()
        self.message_user(request, f"Rejected {queryset.count()} items")
    reject_selected.short_description = "Reject selected"

