# MeritLink Data Pipeline Implementation Plan

## Overview

The data pipeline is the foundation of MeritLink. It ingests scholarship data from external sources and user submissions, processes it through LLM extraction and cleaning, routes it through a human review process, and lands clean, structured, accurate data in the live `Scholarship` model.

**Core Goal**: Deliver a reliable, maintainable pipeline that produces high-quality data suitable for intelligent matching, without relying on dummy data for development.

**Key Principles** (from prior alignment):
- Real data first.
- Human is the final quality gate.
- Once accepted into the live DB, data is "fully cleaned and usable".
- Flexible acceptance (source URL is truth for missing fields).
- Updates are conservative and deadline-driven.
- The external batch script can run locally (development) and as a scheduled task (production).

**Tech Stack for Pipeline**:
- External script: Python + Playwright (fetching) + Gemini Flash-Lite (primary LLM) + Groq fallback.
- Django: `scholarships` app (live model) + `ingestion` app (pipeline concerns).
- Local state for script: SQLite.
- Communication: Management commands (primary for dev) + optional internal API.
- Review: Django admin (customized for full new review + light update review).
- Future: Celery for scheduled/background work.

## Current State (as of 2026-06-29)

- Apps created: `scholarships/`, `ingestion/`.
- Basic models in place for `Scholarship`, `ReviewItem`, `PendingUrl`.
- Some services and management commands started.
- Workflow documented in `docs/data-pipeline-workflow.md`.
- Project uses flat app layout at root (not the `apps/` subdir convention).
- Database: SQLite (will move to PostgreSQL for production).
- No user-facing form or live LLM integration yet.

## High-Level Components

1. **URL Discovery & Submission**
   - Aggregator scrapers (3 sources).
   - User submission form (URL only, tracked as `user_submitted`).

2. **External Batch Script**
   - Config-driven discovery using Playwright.
   - LLM extraction + cleaning.
   - Deduplication using local state.
   - Classify new vs update.
   - Export to JSON or call management command/API.

3. **Ingestion Services (Django)**
   - Cleaning & normalization.
   - Deduplication helpers.
   - Diff generation for updates.

4. **Review Layer**
   - `PendingUrl` for user submissions.
   - `ReviewItem` (unified for new + updates).
   - Full review for new (edit any field).
   - Light review for updates (diffs focused).
   - Force-accept allowed.

5. **Live Data**
   - `Scholarship` model (core fields prioritized for matching).
   - `is_user_submitted` flag + analytics hooks.

6. **Update & Maintenance**
   - Deadline-driven re-checks.
   - Conservative auto-apply only for minor changes.
   - Local script state (last checked, deadlines).

7. **Cross-cutting**
   - Logging, error handling, rate limiting.
   - Security (URL validation, input sanitization).
   - Testing strategy.
   - Monitoring for LLM costs/rate limits.

## Phased Implementation

Phases are designed to be incremental. After **each phase**, perform a full review (code quality, security, tests, maintainability, alignment with pipeline goals). Use sub-agents for reviews where appropriate to avoid context bloat.

### Phase 1: Foundation & Models (1-2 days)

**Objectives**:
- Solid data models.
- Basic migrations and admin setup.
- Project structure locked.

**Tasks**:
- Finalize and enhance `scholarships/models.py` (add indexes, validators, methods, Meta options).
- Enhance `ingestion/models.py` (add signals or hooks if needed, indexes).
- Create and run migrations.
- Set up basic admin customization.
- Add `AGENTS.md` and update docs if needed.
- Basic model tests (pytest or Django tests).

**Deliverables**:
- Working migrations.
- Models ready for pipeline logic.
- Admin lists for ReviewItem and Scholarship.

**Review Criteria (post-phase)**:
- Model design follows Django best practices (proper fields, constraints, no fat models yet).
- Security: No sensitive data in models, proper unique constraints.
- Code quality: Type hints, docstrings, clean.
- Tests: At least basic model validation tests.
- No unnecessary dependencies.

**Gate**: Models approved. No changes to models after this without strong justification.

### Phase 2: Core Services & Cleaning Logic (2-3 days)

**Objectives**:
- Automated cleaning and validation pipeline.
- Deduplication helpers.
- Service layer in `ingestion/services/`.

**Tasks**:
- Implement `cleaning.py` with rules for dates, lists, amounts, text, quality gates (based on suggestions in workflow doc).
- Implement `deduplication.py` (URL + fuzzy title/provider).
- Add diff generation logic for updates.
- Unit tests for cleaning rules (use sample real extractions when available).
- Make cleaning configurable (e.g., via settings or simple config file).

**Deliverables**:
- Functional cleaning that produces usable `cleaned_data`.
- Tests covering edge cases (bad dates, partial data).
- Documentation in services.

**Review Criteria**:
- Cleaning rules are robust but not over-engineered.
- Security: Proper input sanitization (no eval, safe parsing).
- Code quality: Pure functions where possible, good error handling.
- Performance: Efficient for batch processing.
- Review with sample data from real sources.

**Gate**: Cleaning produces consistent output. LLM output can be fed through without crashes.

### Phase 3: Script Integration & Management Commands (2-3 days)

**Objectives**:
- Reliable bridge between external script and Django.
- Local script skeleton that works for development.

**Tasks**:
- Implement `process_ingest_batch` command (fully functional with file input).
- Create `recheck_open_scholarships` command (queues updates).
- Build skeleton for external script (`scripts/ingest.py` or inside ingestion).
  - Playwright setup.
  - Gemini/Groq client with fallback and rate-limit handling.
  - Config for sources (list of base URLs + link selectors).
  - Local SQLite state management (seen URLs, deadlines, last_checked).
  - Export JSON or call management command.
- Basic handling for user-submitted PendingUrls.
- Error logging and retry logic.

**Deliverables**:
- End-to-end: Script can process a small list of URLs and create ReviewItems.
- Local script that runs without Django server (for dev).

**Review Criteria**:
- Script is decoupled from Django where possible.
- Security: Validate all URLs, handle network failures gracefully, no secrets in code.
- Reliability: Proper state management to avoid re-processing.
- Code quality: Clear separation (fetch, extract, clean, classify, push).
- Test the script against 5-10 real URLs from the three sources.

**Gate**: Script successfully populates review items from real sources.

### Phase 4: Review & Approval Workflow (2-3 days)

**Objectives**:
- Usable human review interface.
- Approval logic that creates live Scholarship records.
- Support for full edit on new + light diff view on updates.

**Tasks**:
- Enhance `ReviewItemAdmin` for diffs display, side-by-side editing.
- Implement approval logic: On approve, create/update `Scholarship` from `cleaned_data`.
- Handle force-accept for missing fields.
- Special handling for `user_submitted` flag.
- Basic rejection workflow + notes.
- Simple dashboard stats (e.g., pending count, user submissions).
- Tests for approval flow.

**Deliverables**:
- Working review in Django admin.
- Live Scholarship records created from approved items.
- Update review shows meaningful diffs.

**Review Criteria**:
- UX for founder is efficient (not too many clicks).
- Security: Only staff/superuser access to review.
- Data integrity: Approved records match cleaned_data; source_url preserved.
- Code quality: Approval logic in services, not admin.
- Test with real reviewed data.

**Gate**: Can approve a real item and have it appear as usable data.

### Phase 5: Update & Maintenance Mechanisms (2 days)

**Objectives**:
- Working re-check and update flow.
- Conservative update policy implemented.

**Tasks**:
- Script re-check logic (deadline-driven using live data + local state).
- Generate diffs between current Scholarship and new cleaned data.
- Auto-apply only for minor changes (configurable threshold).
- Queue most changes to light review.
- Handle edge cases (page 404, deadline passed, major eligibility change).
- Update `last_verified` and status fields.
- Tests for update classification.

**Deliverables**:
- End-to-end update from re-extraction to live data or review.
- No data loss on re-checks.

**Review Criteria**:
- Updates respect "very conservative" policy.
- Security: Re-fetches are rate-limited; no blind trust in new extractions.
- Maintainability: Clear classification rules.
- Test with real data where deadlines have changed.

**Gate**: Can re-check an approved scholarship and see controlled update path.

### Phase 6: User Submissions & Tracking (1-2 days)

**Objectives**:
- Public form for URL submission.
- Tracking and queueing of user submissions.

**Tasks**:
- Simple form (HTMX-friendly) that saves to `PendingUrl`.
- Mark items as `user_submitted`.
- Admin visibility and stats for submissions.
- Script integration to pull/process pending URLs.
- Basic anti-spam (simple rate limit or captcha later).
- Analytics hooks (count of user submissions).

**Deliverables**:
- Functional submission flow.
- Submissions appear in review queue with flag.

**Review Criteria**:
- Security: URL validation, no arbitrary code execution.
- UX: Simple (just URL).
- Tracking works for reporting.

**Gate**: User can submit a URL and it reaches review.

### Phase 7: Polish, Testing, Security & Hardening (2-3 days)

**Objectives**:
- Production-ready pipeline components.
- Comprehensive testing and review.

**Tasks**:
- Full test coverage (unit for services, integration for commands/flow).
- Logging and monitoring hooks (LLM usage, errors, review queue size).
- Rate limiting and retry for LLM calls.
- Error handling and graceful degradation.
- Security audit (input validation, no secrets leaked, safe scraping).
- Basic documentation for running the script and review process.
- Move toward PostgreSQL compatibility (ArrayField or keep JSON).
- Performance: Batch sizes, parallel fetching if safe.

**Deliverables**:
- Test suite.
- Security review checklist passed.
- Script can be run periodically without issues.
- All prior phases' code reviewed and cleaned.

**Review Criteria**:
- Code quality: Consistent style, no duplication, good separation.
- Security: OWASP considerations for ingestion (untrusted URLs/HTML).
- Reliability: Handles failures without corrupting data.
- Use sub-agent for independent security/code quality review.

**Gate**: Pipeline is trustworthy for real data. Ready for matching work.

### Phase 8: Future Extensions (as needed)

- Celery tasks for background processing.
- LLM prompt versioning and evaluation.
- Richer diff UI.
- Automated confidence scoring to prioritize review.
- Self-submission improvements (login, more fields later).
- Analytics dashboard for pipeline health.

## Review Process After Each Phase

- Run full test suite.
- Manual review of code (or spawn reviewer sub-agent).
- Security checklist (from global practices + Django security patterns).
- Data quality: Feed real examples and inspect output.
- Context: Keep changes minimal and focused.
- Document decisions in the plan or workflow doc.
- Only proceed after explicit approval of the phase.

## Risks & Mitigations

- LLM inconsistency: Strong cleaning + human gate.
- Scraping breakage: Config-driven + Playwright; monitor sources.
- Data volume: Efficient state + selective re-checks.
- Security (malicious URLs): Strict validation, no auto-execute.
- Founder time for review: Keep UI lightweight; conservative updates.

## Success Metrics

- Can ingest 50+ real scholarships with <30 min founder review time.
- Updates surface only meaningful changes.
- Clean data ready for matching engine.
- Script runs reliably both locally and scheduled.

---

This plan is derived from the established workflow. Adjust phases based on velocity after Phase 1 review.