import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.crawl_state import CrawlState
from scripts.sources import SOURCES, SourceConfig

DEFAULT_DB_PATH = Path(__file__).parent / "crawl_state.db"


def main() -> int:
    """Entry point for the discovery script."""
    parser = argparse.ArgumentParser(
        description="Discover scholarship URLs by crawling aggregator listing pages."
    )
    parser.add_argument(
        "--source",
        required=True,
        choices=list(SOURCES.keys()),
        help="Source name (key in SOURCES dict).",
    )
    parser.add_argument(
        "--import-urls",
        action="append",
        default=[],
        help="JSON file of URLs to import (can be passed multiple times).",
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="Path to the local crawl state SQLite DB.",
    )
    args = parser.parse_args()

    source = SOURCES[args.source]
    state = CrawlState(Path(args.db_path))
    state.initialize()

    imported_count = 0
    for file_path in args.import_urls:
        path = Path(file_path)
        with path.open() as f:
            entries = json.load(f)
        for entry in entries:
            url = entry.get("url")
            if not url:
                continue
            state.record_discovery(
                url, source="manual_retry", user_submitted=True, force_requeue=True
            )
            imported_count += 1
        print(f"Imported {len(entries)} URLs from {file_path}")

    new_count = 0
    known_count = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            seen_in_run: set[str] = set()
            for page_num in range(1, source.max_pages + 1):
                listing_url = source.listing_url_pattern.format(page=page_num)
                print(f"Discovering: {listing_url}")
                try:
                    page.goto(listing_url, wait_until="domcontentloaded", timeout=30000)
                except Exception as exc:
                    print(f"  Failed to load listing page {page_num}: {exc}", file=sys.stderr)
                    continue
                try:
                    page.wait_for_selector(source.listing_selector, timeout=5000)
                except Exception:
                    pass
                links = _extract_listing_links(page, source)
                for href in links:
                    absolute = urljoin(source.base_url, href)
                    if not _is_internal(source, absolute):
                        continue
                    if absolute in seen_in_run:
                        continue
                    seen_in_run.add(absolute)
                    already_seen = state.has_been_seen(absolute)
                    state.record_discovery(
                        absolute, source=source.name, user_submitted=False
                    )
                    if already_seen:
                        known_count += 1
                    else:
                        new_count += 1
            page.close()
        finally:
            browser.close()

    state.close()

    total = new_count + known_count
    print(f"Discovered {total} URLs ({new_count} new, {known_count} already known).")
    if args.import_urls:
        files_str = ", ".join(args.import_urls)
        print(f"Imported {imported_count} URLs from {files_str}.")
    return 0


def _extract_listing_links(page: Page, source: SourceConfig) -> list[str]:
    """Extract href values from listing page using the source selector."""
    hrefs: list[str] = []
    try:
        elements = page.query_selector_all(source.listing_selector)
    except Exception as exc:
        print(f"  Selector query failed: {exc}", file=sys.stderr)
        return hrefs
    for el in elements:
        try:
            href = el.get_attribute("href")
        except Exception:
            continue
        if href:
            hrefs.append(href)
    return hrefs


def _is_internal(source: SourceConfig, url: str) -> bool:
    """Check whether a URL belongs to the source's domain."""
    try:
        host = urlparse(url).netloc
    except Exception:
        return False
    source_host = urlparse(source.base_url).netloc
    return host == source_host


if __name__ == "__main__":
    raise SystemExit(main())
