from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import Scholarship


@staff_member_required
@require_POST
def queue_recheck(request, pk: int):
    """Queue a single scholarship for manual recheck."""
    import sqlite3
    from datetime import date
    from pathlib import Path
    from django.conf import settings

    scholarship = get_object_or_404(Scholarship, pk=pk)
    db_path = Path(settings.BASE_DIR) / "scripts" / "crawl_state.db"
    today = date.today().isoformat()
    deadline = scholarship.application_deadline.isoformat() if scholarship.application_deadline else None
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
    conn.commit()
    conn.close()
    messages.success(request, f"Queued for recheck: {scholarship.title}")
    return redirect("admin:scholarships_scholarship_change", object_id=pk)
