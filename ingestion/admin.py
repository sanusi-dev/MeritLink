from django.contrib import admin
from django.utils.html import format_html

from .models import PendingUrl, ReviewItem


@admin.register(PendingUrl)
class PendingUrlAdmin(admin.ModelAdmin):
    list_display = ["url", "submitted_at", "processed"]
    list_filter = ["processed"]
    search_fields = ["url"]
    actions = ["mark_as_unprocessed"]

    def mark_as_unprocessed(self, request, queryset):
        queryset.update(processed=False)
    mark_as_unprocessed.short_description = "Mark selected as unprocessed"


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
        for item in queryset.filter(status="pending"):
            # In real usage you would also create/update the Scholarship here
            # For now we just mark approved (you can wire the logic later)
            item.mark_approved()
        self.message_user(request, f"Approved {queryset.count()} items")
    approve_selected.short_description = "Approve selected (mark only)"

    def reject_selected(self, request, queryset):
        for item in queryset.filter(status="pending"):
            item.mark_rejected()
        self.message_user(request, f"Rejected {queryset.count()} items")
    reject_selected.short_description = "Reject selected"

