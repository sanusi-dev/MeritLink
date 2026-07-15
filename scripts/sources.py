from dataclasses import dataclass


@dataclass
class SourceConfig:
    name: str
    base_url: str
    listing_selector: str
    listing_url_pattern: str
    max_pages: int


SOURCES: dict[str, SourceConfig] = {
    "afterschoolafrica": SourceConfig(
        name="AfterSchool Africa",
        base_url="https://afterschoolafrica.com",
        listing_url_pattern="https://afterschoolafrica.com/scholarships/page/{page}/",
        # Broad selectors to catch scholarship links across layout changes.
        # May need adjustment after testing against the real site.
        listing_selector="article h2 a, .scholarship-listing a, .entry-title a",
        max_pages=3,
    ),
}
