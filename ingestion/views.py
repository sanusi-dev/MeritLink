import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render

from django.views.decorators.http import require_POST

from scholarships.models import Scholarship
from .forms import ReviewForm
from .models import ReviewItem
from .services.approval import approve_review_item


@staff_member_required
def review_list(request):
    """Render the review queue with optional type filter tabs."""
    item_type = request.GET.get("type")
    pending = ReviewItem.objects.filter(status="pending").order_by("-created_at")
    if item_type in ("new", "update"):
        pending = pending.filter(review_type=item_type)

    counts = {
        "all": ReviewItem.objects.filter(status="pending").count(),
        "new": ReviewItem.objects.filter(status="pending", review_type="new").count(),
        "update": ReviewItem.objects.filter(status="pending", review_type="update").count(),
    }

    recently_approved = ReviewItem.objects.filter(status="approved").order_by("-reviewed_at")[:5]
    recently_rejected = ReviewItem.objects.filter(status="rejected").order_by("-reviewed_at")[:5]

    return render(request, "ingestion/review_list.html", {
        "pending": pending,
        "counts": counts,
        "active_tab": item_type or "all",
        "recently_approved": recently_approved,
        "recently_rejected": recently_rejected,
    })


@staff_member_required
def review_detail(request, pk: int):
    review_item = get_object_or_404(ReviewItem, pk=pk)

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            if review_item.status != "pending":
                messages.error(request, "This item is no longer pending.")
                return redirect("ingestion:review_list")

            if "approve" in request.POST:
                try:
                    approve_review_item(review_item, overrides=form.get_overrides())
                    messages.success(
                        request,
                        f"Approved and saved to live database: {review_item.source_url}",
                    )
                    return redirect("ingestion:review_list")
                except Scholarship.DoesNotExist:
                    messages.error(
                        request,
                        "Cannot approve update: no existing Scholarship found for this URL.",
                    )
            elif "reject" in request.POST:
                review_item.mark_rejected()
                messages.info(request, f"Rejected: {review_item.source_url}")
                return redirect("ingestion:review_list")
    else:
        initial = ReviewForm.prepare_initial(review_item.cleaned_data)
        form = ReviewForm(initial=initial)

    return render(request, "ingestion/review_detail.html", {
        "form": form,
        "review_item": review_item,
    })


@staff_member_required
@require_POST
def run_queue(request):
    """Trigger process.py in the background to drain the extraction queue."""
    from scripts.lockfile import is_locked

    lock_path = Path(settings.BASE_DIR) / "scripts" / "llm_extraction.lock"

    if is_locked(lock_path):
        messages.info(request, "Processing is already in progress — please wait.")
        return redirect("ingestion:review_list")

    limit = request.POST.get("limit", "5")
    log_path = Path(settings.BASE_DIR) / "logs" / "process_run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "a") as log_file:
        subprocess.Popen(
            [
                sys.executable,
                str(Path(settings.BASE_DIR) / "scripts" / "process.py"),
                "--source", "afterschoolafrica",
                "--limit", limit,
            ],
            cwd=str(settings.BASE_DIR),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    messages.success(request, "Processing started in the background — check the Updates queue in a few minutes.")
    return redirect("ingestion:review_list")
