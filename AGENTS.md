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

These instructions take precedence for all work on the MeritLink codebase.