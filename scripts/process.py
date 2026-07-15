import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.crawl_state import CrawlState
from scripts.extraction_helpers import extract_single, resolve_output_path, write_output
from scripts.lockfile import acquire_lock, release_lock
from scripts.sources import SOURCES

DEFAULT_DB_PATH = Path(__file__).parent / "crawl_state.db"
LOCK_PATH = Path(__file__).parent / "llm_extraction.lock"
MANAGE_PY = str(Path(__file__).resolve().parent.parent / "manage.py")


def main() -> int:
    """Entry point for the extraction script."""
    parser = argparse.ArgumentParser(
        description="Extract scholarship data from discovered URLs via LLM."
    )
    parser.add_argument(
        "--source",
        required=True,
        choices=list(SOURCES.keys()),
        help="Source name (key in SOURCES dict).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Max URLs to process (default: 5).",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output file path (default: exports/review_items_YYYY-MM-DD.json).",
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="Path to the local crawl state SQLite DB.",
    )
    args = parser.parse_args()

    source = SOURCES[args.source]

    lock_file = acquire_lock(LOCK_PATH)
    if lock_file is None:
        print("Another extraction process is already running — exiting.")
        return 0

    state: CrawlState | None = None
    try:
        state = CrawlState(Path(args.db_path))
        state.initialize()

        pending = state.get_pending_urls(source.name, args.limit)
        if not pending:
            print("No URLs to process.")
            return 0

        output_path = resolve_output_path(args.output, "review_items")
        items: list[dict] = []
        session_failures: list[dict] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                for i, (url, user_submitted) in enumerate(pending, 1):
                    print(f"[{i}/{len(pending)}] {url}")
                    try:
                        data = extract_single(browser, url)
                        data["is_user_submitted"] = user_submitted
                        items.append(data)
                        state.mark_processed(
                            url, deadline=data.get("application_deadline")
                        )
                        print(f"  ✓ extracted: {data.get('title', '(no title)')[:80]}")
                    except Exception as exc:
                        if isinstance(exc, PlaywrightError) or isinstance(
                            exc, TimeoutError
                        ):
                            failure_type = "fetch"
                        else:
                            failure_type = "extraction"
                        attempts = state.record_failure(
                            url, failure_type, error=str(exc)
                        )
                        session_failures.append(
                            {
                                "url": url,
                                "failure_type": failure_type,
                                "error": str(exc),
                                "attempts": attempts,
                            }
                        )
                        print(f"  ✗ failed: {exc}", file=sys.stderr)
            finally:
                browser.close()

        write_output(items, output_path)

        if session_failures:
            temp_path = Path(f"/tmp/session_failures_{date.today().isoformat()}.json")
            with temp_path.open("w") as f:
                json.dump(session_failures, f, indent=2)
            subprocess.call(
                [sys.executable, MANAGE_PY, "import_session_failures", str(temp_path)]
            )
            print(f"Pushed {len(session_failures)} failures to PendingUrl table")

        print(
            f"Processed {len(pending)} URLs → {len(items)} extracted, "
            f"{len(session_failures)} failed → saved to {output_path}"
        )
        return 0
    finally:
        if state is not None:
            state.close()
        release_lock(lock_file)


if __name__ == "__main__":
    raise SystemExit(main())
