"""Shared helpers for process.py and future recheck scripts."""
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.llm_client import extract_with_llm


def fetch_html(browser: Browser, url: str) -> str:
    """Fetch page HTML with Playwright. New context per URL."""
    context = browser.new_context()
    page = context.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        return page.content()
    finally:
        context.close()


def extract_single(browser: Browser, url: str) -> dict[str, Any]:
    """Fetch + LLM extract for a single URL. Returns dict with source_url set.
    Raises on fetch or extraction failure (caller catches)."""
    html = fetch_html(browser, url)
    data = extract_with_llm(html, url)
    if not isinstance(data, dict):
        raise ValueError("LLM did not return a JSON object")
    data.setdefault("source_url", url)
    return data


def resolve_output_path(output: str, prefix: str) -> Path:
    """Resolve output path. If output is empty, defaults to exports/{prefix}_{date}.json."""
    if output:
        return Path(output)
    exports_dir = Path(__file__).resolve().parent.parent / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    return exports_dir / f"{prefix}_{date.today().isoformat()}.json"


def write_output(items: list[dict], path: Path) -> None:
    """Write items to JSON file with indent=2, ensure_ascii=False."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
