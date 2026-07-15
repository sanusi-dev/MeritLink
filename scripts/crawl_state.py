import sqlite3
from datetime import date
from pathlib import Path


class CrawlState:
    """Local SQLite state for tracking crawled URLs between runs."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def initialize(self) -> None:
        """Create tables if they don't exist, migrate old schemas, and open the connection."""
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crawled_urls (
                url TEXT PRIMARY KEY,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                last_checked TEXT NOT NULL,
                known_deadline TEXT,
                status TEXT NOT NULL DEFAULT 'discovered',
                failure_type TEXT,
                attempts INTEGER DEFAULT 0,
                last_error TEXT,
                source TEXT,
                user_submitted INTEGER DEFAULT 0
            )
            """
        )
        for column, definition in [
            ("last_seen", "TEXT"),
            ("failure_type", "TEXT"),
            ("attempts", "INTEGER DEFAULT 0"),
            ("last_error", "TEXT"),
            ("user_submitted", "INTEGER DEFAULT 0"),
        ]:
            try:
                self._conn.execute(
                    f"ALTER TABLE crawled_urls ADD COLUMN {column} {definition}"
                )
            except sqlite3.OperationalError:
                pass
        self._conn.execute(
            "UPDATE crawled_urls SET status = 'processed' WHERE status = 'ok'"
        )
        self._conn.execute(
            "UPDATE crawled_urls SET last_seen = last_checked WHERE last_seen IS NULL"
        )
        self._conn.commit()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("CrawlState not initialized. Call initialize() first.")
        return self._conn

    def record_discovery(
        self,
        url: str,
        source: str,
        user_submitted: bool = False,
        force_requeue: bool = False,
    ) -> None:
        """Upsert a URL. Never downgrades status unless force_requeue=True.

        New URL -> INSERT with status='discovered', first_seen=last_seen=last_checked=today.
        Existing URL -> UPDATE last_seen=today only. Status, attempts, last_error untouched.
        If force_requeue=True and status='failed' -> downgrade to 'discovered',
        reset attempts=0, last_error=NULL.
        """
        today = date.today().isoformat()
        cur = self.conn.execute(
            "SELECT status FROM crawled_urls WHERE url = ?", (url,)
        )
        row = cur.fetchone()
        if row is None:
            self.conn.execute(
                """
                INSERT INTO crawled_urls
                (url, first_seen, last_seen, last_checked, known_deadline, status,
                 failure_type, attempts, last_error, source, user_submitted)
                VALUES (?, ?, ?, ?, NULL, 'discovered', NULL, 0, NULL, ?, ?)
                """,
                (url, today, today, today, source, 1 if user_submitted else 0),
            )
        elif force_requeue and row[0] == "failed":
            self.conn.execute(
                """
                UPDATE crawled_urls
                SET status = 'discovered', last_seen = ?, attempts = 0, last_error = NULL
                WHERE url = ?
                """,
                (today, url),
            )
        else:
            self.conn.execute(
                "UPDATE crawled_urls SET last_seen = ? WHERE url = ?",
                (today, url),
            )
        self.conn.commit()

    def get_pending_urls(self, source: str, limit: int) -> list[tuple[str, bool]]:
        """Return (url, user_submitted) tuples where status='discovered',
        oldest first_seen, capped at limit."""
        cur = self.conn.execute(
            """
            SELECT url, user_submitted FROM crawled_urls
            WHERE status = 'discovered' AND source = ?
            ORDER BY first_seen ASC
            LIMIT ?
            """,
            (source, limit),
        )
        return [(row[0], bool(row[1])) for row in cur.fetchall()]

    def mark_processed(self, url: str, deadline: str | None = None) -> None:
        """Set status='processed', known_deadline=deadline, last_checked=today,
        attempts=0, last_error=NULL."""
        today = date.today().isoformat()
        self.conn.execute(
            """
            UPDATE crawled_urls
            SET status = 'processed', known_deadline = ?, last_checked = ?,
                attempts = 0, last_error = NULL
            WHERE url = ?
            """,
            (deadline, today, url),
        )
        self.conn.commit()

    def record_failure(self, url: str, failure_type: str, error: str) -> int:
        """Increment attempts. If attempts >= 3, set status='failed'.
        Store failure_type + last_error. Update last_checked.
        Returns the new attempt count."""
        today = date.today().isoformat()
        self.conn.execute(
            """
            UPDATE crawled_urls
            SET attempts = attempts + 1,
                failure_type = ?,
                last_error = ?,
                last_checked = ?,
                status = CASE WHEN attempts + 1 >= 3 THEN 'failed' ELSE status END
            WHERE url = ?
            """,
            (failure_type, error, today, url),
        )
        self.conn.commit()
        cur = self.conn.execute(
            "SELECT attempts FROM crawled_urls WHERE url = ?", (url,)
        )
        row = cur.fetchone()
        return row[0] if row else 0

    def has_been_seen(self, url: str) -> bool:
        """Check if URL exists in the table."""
        cur = self.conn.execute(
            "SELECT 1 FROM crawled_urls WHERE url = ?", (url,)
        )
        return cur.fetchone() is not None

    def get_known_deadline(self, url: str) -> str | None:
        """Get the known_deadline for a URL, or None."""
        cur = self.conn.execute(
            "SELECT known_deadline FROM crawled_urls WHERE url = ?", (url,)
        )
        row = cur.fetchone()
        return row[0] if row else None

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
