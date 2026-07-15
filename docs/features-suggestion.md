# Features Suggestion Log

Records ideas and constraints discovered during pipeline development
that affect future user-facing features. Append as new insights emerge.

## "Last Verified" Display on Scholarship Listings

Each scholarship detail page (when built) should display:
  "Last verified X days ago — please confirm details on the official page"
with a link to `source_url`.

**Why:** We don't continuously monitor scholarship pages. Data is a
snapshot from our last extraction. Surfacing `last_verified` (from
Scholarship model) as relative time is more trustworthy than a generic
disclaimer.

**Data source:** `Scholarship.last_verified` (set on approval).
Format: "4 days ago", "2 weeks ago", "3 months ago".

## Recheck Strategy — UNRESOLVED

Automatic re-extraction of live scholarships is currently manual only.

**Problem:** Naive re-extraction (fetch + LLM extract every URL with a
future deadline) doesn't scale:
- No way to detect if a page changed since last extraction — we'd
  re-extract unchanged pages, wasting API calls
- As the DB grows to thousands of scholarships, the recheck volume
  exceeds free tier limits and is uneconomical on paid tiers
- Free tier budget must be shared between new discoveries AND rechecks

**What we need before implementing auto-recheck:**
1. A cheap change-detection mechanism (e.g., compare page HTML hash
   with last fetch — if unchanged, skip LLM extraction entirely)
2. Priority scoring (scholarships with deadlines approaching soonest
   get rechecked first)
3. Budget-aware scheduling (if daily API budget is 50 calls and 40
   new URLs are in the queue, only 10 rechecks run that day)

**Current approach:** Manual recheck via admin. Scholarship admin has
"Queue for Recheck" button (single) and "Queue Selected for Recheck"
bulk action. Admin clicks "Run Queue Now" on the review page to
trigger process.py in the background. Results appear in the Updates
tab of the review queue.

## Failed URL Recovery

Failed extraction URLs are pushed to Django's PendingUrl table after
every process.py session via the `import_session_failures` management
command. Admin reviews failures (with error type and message) in
PendingUrl admin, selects URLs worth retrying, exports to JSON via
"Export Selected to JSON" admin action. Next `discover.py --import-urls`
run picks them up and re-queues them in crawl_state.db.

**Error types stored:** `fetch` (Playwright/network failures) vs
`extraction` (LLM parsing failures). This helps the admin decide
which failures are worth retrying — fetch failures may be transient
(bot blocks, timeouts), while extraction failures may indicate the
page isn't a real scholarship page.
