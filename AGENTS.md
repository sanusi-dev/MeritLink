# MeritLink Agent Instructions

## Core Operating Principles

- Be direct and concise. Lead with the answer, decision, or next action. Skip filler.
- Never repeat the user's query or previous statements before responding.
- Do not use phrases like "you're absolutely right", "great point", or similar validation language.
- Follow Django best practices: proper model design, service layers for complex logic, management commands for CLI operations, clear app boundaries, and separation of concerns.
- Write clean, readable, maintainable code. Use meaningful names, docstrings for public functions and models, type hints where they improve clarity, and avoid unnecessary complexity.
- Prefer small, focused changes. Test incrementally.

## Task Execution

- When a task is large, complex, involves multiple distinct concerns, or can run in parallel, split it across multiple specialized sub-agents using the available spawn mechanism.
- Use sub-agents for parallel work (e.g., one for models, one for services, one for commands) to keep individual context windows manageable and reduce wait time.
- The main agent coordinates but does not perform every sub-task itself.
- For reviews after each phase (code quality, security, tests, maintainability), spawn a dedicated reviewer sub-agent.
- After every big implementation (new feature, multi-file change, phase completion), always spawn a dedicated sub-agent to review the work for code quality, security, test coverage, and alignment before reporting back to the user.
- Always maintain and update the todo list throughout the work — mark items in_progress when starting, completed when done, and add follow-ups discovered during work. Never batch completions or leave the todo list stale.

## File and Code Changes

- Before creating or editing any file, confirm the exact target path.
- Never overwrite an existing file without explicit confirmation from the user.
- After creating a new file or making significant edits, report the absolute path of the affected file(s).
- Use precise tools for changes: search/replace for targeted edits, dedicated write for new files.
- Run Django management commands (e.g., makemigrations, test) via the project's virtual environment activation when needed.
- Keep changes aligned with the current implementation plan in `docs/data-pipeline-implementation-plan.md`.

## Project-Specific Guidelines

- Respect the established app boundaries:
  - `scholarships/`: owns the live `Scholarship` model and domain queries.
  - `ingestion/`: owns pipeline concerns (ReviewItem, PendingUrl, cleaning, review flow, management commands).
- All live data must pass through the review layer before becoming usable.
- User-submitted items must be explicitly tracked with the `user_submitted` flag.
- Updates are conservative and deadline-driven by default.
- External script uses Playwright + LLM (Gemini primary, Groq fallback) and communicates via management commands (primary) or API.
- Security: validate all external URLs and inputs. No blind trust in LLM output. Human review is the final gate.
- After every phase in the data pipeline plan, perform explicit review of code quality, security, tests, and alignment before proceeding.

## Efficiency and Context Management

- Split work across agents early when it reduces context pressure or enables parallelism.
- Prefer focused, single-responsibility sub-tasks.
- Document decisions only when they affect future work or the plan.

## Technical Reference

Verified against the codebase; where the README conflicts with config, config wins.

### Stack

- Python **>=3.14** (`pyproject.toml`), Django 6.0.5, SQLite (`db.sqlite3` at root).
- README describes a *planned* stack (PostgreSQL, Celery+Redis, django-allauth, additional apps) — **none of that exists yet**.
- `main.py` is an unused stub. Real entrypoint is `manage.py`.
- Django settings module is **`MeritLink.settings`** (capital `M` and `L`).

### Environment & Commands

- Uses **uv**, not pip. No `requirements.txt`.
  - Sync deps: `uv sync`
  - Run anything: `uv run python manage.py ...`
- `uv run python manage.py test` — full suite; `uv run python manage.py test app.tests.test_module` — single file.
- `uv run djlint .` — lint/format Django templates.
- No black/flake8/pytest installed. No CI, no pre-commit hooks. Branch: `main`.

### Frontend Assets (gitignored — must be rebuilt)

Vendored files (`static/js/htmx.min.js`, `static/js/sweetalert2.min.js`, `static/css/sweetalert2.min.css`) and compiled Tailwind output (`static/css/output.css`) are all in `.gitignore`.

```bash
npm install && npm run build       # vendor:copy + build:css
npm run watch:css                  # rebuild Tailwind on save during dev
```

`tailwind.config.js` scans `templates/**/*.html`, `core/templates/**/*.html`, `**/templates/**/*.html`, `**/*.py`. New template dirs outside these patterns won't be picked up.

### App Architecture

Three apps at root level (flat layout, not `apps/` subdir):

- **`core/`** — shared utilities, middleware. URL namespace `core`, mounted at root `""`.
- **`scholarships/`** — owns the live `Scholarship` model (clean, usable data). `managers.py` and `selectors.py` exist but are empty.
- **`ingestion/`** — owns pipeline concerns: `ReviewItem`, `PendingUrl`, `services/cleaning.py`, `services/deduplication.py`, `management/commands/`. Depends on `scholarships`.

Templates: project-level `templates/base.html` (via `TEMPLATES DIRS`), app-level `*/templates/*/*.html` (via `APP_DIRS`).

### HTMX + SweetAlert2 Message Wiring (non-obvious, cross-cutting)

`core/middleware.py` `HtmxMessageMiddleware` serializes Django `messages` into the `HX-Trigger: showMessages` response header for HTMX requests. `templates/base.html` has JS that renders these as SweetAlert2 toasts on both full page loads and HTMX swaps. Touch this wiring carefully — message display depends on it end-to-end.

### Pipeline State (as of 2026-07-15)

- Phase 1 (models + admin scaffolds) done. Migrations created and applied. Models and admin functional. Model tests pass.
- Phase 2 (cleaning services) ~70% — `_normalize_date` now parses 11 formats + ordinal suffixes → ISO strings. `_normalize_countries` and `_normalize_study_levels` standardize 40+ variants each. `_parse_amount` extracts currency/amount with regex, aligned with `FundingAmountDetails` Pydantic schema. Quality gates: hard fail on missing title/source_url, warn on missing deadline/study levels. `extraction_confidence` derived from `_quality_status` (ok=1.0, warn=0.6, fail=0.2). Diff generation implemented (`ingestion/services/diff.py`). Dedup is still URL-exact only (`is_duplicate` returns `False`).
- Phase 3 (commands + script) ~80% — **Pipeline decoupled into 3 scripts**: `scripts/discover.py` (weekly listing crawl, no LLM, stores URLs in crawl_state.db), `scripts/process.py` (daily queue drain, fetch + LLM extract, pushes failures to Django PendingUrl), `scripts/ingest.py` deleted. `scripts/lockfile.py` uses `fcntl.flock` to prevent concurrent process.py runs. `scripts/extraction_helpers.py` shared fetch/extract helpers. `scripts/crawl_state.py` rewritten with queue workflow (discovered → processed / failed, attempts tracking, failure_type). LLM extraction uses Pydantic `ScholarshipSchema` + `FundingAmountDetails` for structured output. `process_ingest_batch` functional. `recheck_open_scholarships` is still a skeleton (unused). Not yet tested against real pages.
- Phase 4 (review workflow) ~90% — admin approve action calls `approve_review_item()`. Custom review page at `/ingestion/review/` with form editing, overrides, approve/reject. **Filter tabs**: All | New | Updates. **Manual recheck**: Scholarship admin has "Queue for Recheck" button + bulk action. "Run Queue Now" button on review page triggers `process.py` via subprocess. `import_session_failures` command pushes failed URLs to PendingUrl after each process.py session. PendingUrl admin has "Export Selected to JSON" for re-queuing failed URLs. Diff generation service exists but not yet wired into the review UI.
- Phase 5 (update & maintenance) ~20% — Manual recheck via admin (Queue + Run Queue). No auto-recheck until resource-efficient change-detection strategy exists (see `docs/features-suggestion.md`). `recheck_open_scholarships` command is a skeleton (unused).
- Phase 6 (user submissions) ~10% — PendingUrl model handles both user submissions and failed extractions (source field distinguishes them). No public form yet.
- Phases 7–8: not started.
- 250 tests across all apps. Test files are `tests/` packages (not `tests.py`).
- Implementation plan: `docs/data-pipeline-implementation-plan.md`. Workflow spec: `docs/data-pipeline-workflow.md`. Feature suggestions: `docs/features-suggestion.md`.

These instructions take precedence for all work on the MeritLink codebase.