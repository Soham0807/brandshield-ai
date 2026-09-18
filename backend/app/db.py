"""SQLite storage layer.

SQLite keeps the project zero-setup on a laptop. All access goes through this
module, so it can be replaced by MongoDB / PostgreSQL (TimescaleDB) without
touching the rest of the code.
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS mentions (
    id            TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    external_id   TEXT,
    author        TEXT,
    text          TEXT NOT NULL,
    clean_text    TEXT,
    keywords      TEXT,
    url           TEXT,
    language      TEXT,
    created_at    TEXT NOT NULL,
    ingested_at   TEXT NOT NULL,
    processed_at  TEXT NOT NULL,
    sentiment     TEXT NOT NULL,
    confidence    REAL NOT NULL,
    score         REAL NOT NULL,
    probs         TEXT,
    aspects       TEXT,
    is_spam       INTEGER NOT NULL DEFAULT 0,
    spam_reason   TEXT,
    engagement    INTEGER NOT NULL DEFAULT 0,
    true_label    TEXT
);
CREATE INDEX IF NOT EXISTS idx_mentions_created ON mentions(created_at);
CREATE INDEX IF NOT EXISTS idx_mentions_sentiment ON mentions(sentiment);
CREATE INDEX IF NOT EXISTS idx_mentions_source ON mentions(source);

CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    severity    TEXT NOT NULL,
    type        TEXT NOT NULL,
    dedupe_key  TEXT,
    title       TEXT NOT NULL,
    message     TEXT NOT NULL,
    meta        TEXT,
    status      TEXT NOT NULL DEFAULT 'open',
    updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS instagram_accounts (
    ig_user_id          TEXT PRIMARY KEY,
    username            TEXT NOT NULL,
    name                TEXT,
    account_type        TEXT,
    profile_picture_url TEXT,
    followers_count     INTEGER,
    follows_count       INTEGER,
    media_count         INTEGER,
    access_token        TEXT NOT NULL,   -- encrypted
    token_expires_at    TEXT,
    token_refreshed_at  TEXT,
    connected_at        TEXT NOT NULL,
    last_sync_at        TEXT,
    last_error          TEXT
);

CREATE TABLE IF NOT EXISTS instagram_media (
    id              TEXT PRIMARY KEY,
    ig_user_id      TEXT NOT NULL,
    caption         TEXT,
    media_type      TEXT,
    media_url       TEXT,
    thumbnail_url   TEXT,
    permalink       TEXT,
    timestamp       TEXT,
    like_count      INTEGER,
    comments_count  INTEGER,
    synced_comments INTEGER,
    updated_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_media_user ON instagram_media(ig_user_id, timestamp);

CREATE TABLE IF NOT EXISTS youtube_channels (
    channel_id       TEXT PRIMARY KEY,
    handle           TEXT,
    title            TEXT,
    description      TEXT,
    thumbnail_url    TEXT,
    country          TEXT,
    published_at     TEXT,
    subscriber_count INTEGER,
    video_count      INTEGER,
    view_count       INTEGER,
    uploads_playlist TEXT,
    added_at         TEXT NOT NULL,
    last_sync_at     TEXT,
    last_error       TEXT
);

CREATE TABLE IF NOT EXISTS youtube_videos (
    id              TEXT PRIMARY KEY,
    channel_id      TEXT NOT NULL,
    title           TEXT,
    description     TEXT,
    thumbnail_url   TEXT,
    published_at    TEXT,
    view_count      INTEGER,
    like_count      INTEGER,
    comment_count   INTEGER,
    synced_comments INTEGER,
    updated_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_videos_channel ON youtube_videos(channel_id, published_at);
"""

# columns added after the first release: (table, column, definition, backfill SQL)
MIGRATIONS = [
    ("mentions", "origin", "TEXT NOT NULL DEFAULT 'live'",
     # before this column existed, every instagram/twitter/reddit/google_reviews row came from the simulator
     "UPDATE mentions SET origin = 'simulated' "
     "WHERE source IN ('instagram', 'twitter', 'reddit', 'google_reviews')"),
    ("mentions", "parent_id", "TEXT", None),
]

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(TIME_FORMAT)


def from_iso(value: str) -> datetime:
    return datetime.strptime(value, TIME_FORMAT).replace(tzinfo=timezone.utc)


def parse_any_datetime(value) -> datetime:
    """Parse timestamps coming from external APIs / CSV files."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.astimezone()
    if not value:
        return utcnow()
    text = str(value).strip().replace("Z", "+00:00")
    for candidate in (text, text.replace(" ", "T")):
        try:
            dt = datetime.fromisoformat(candidate)
            # timestamps without a zone (CSV exports) are in the machine's local time
            return dt if dt.tzinfo else dt.astimezone()
        except ValueError:
            continue
    for fmt in ("%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).astimezone()
        except ValueError:
            continue
    return utcnow()


MENTION_COLUMNS = [
    "id", "source", "external_id", "author", "text", "clean_text", "keywords",
    "url", "language", "created_at", "ingested_at", "processed_at", "sentiment",
    "confidence", "score", "probs", "aspects", "is_spam", "spam_reason",
    "engagement", "true_label", "origin", "parent_id",
]


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        for table, column, definition, backfill in MIGRATIONS:
            columns = {r[1] for r in self._conn.execute(f"PRAGMA table_info({table})")}
            if column not in columns:
                self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                if backfill:
                    self._conn.execute(backfill)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_mentions_parent ON mentions(parent_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_mentions_origin ON mentions(origin)")

    # ---- generic helpers ------------------------------------------------
    def query(self, sql: str, params=()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def scalar(self, sql: str, params=()):
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
            return row[0] if row else None

    def execute(self, sql: str, params=()) -> int:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur.lastrowid

    def close(self):
        with self._lock:
            self._conn.close()

    # ---- mentions -------------------------------------------------------
    def insert_mentions(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        placeholders = ",".join("?" for _ in MENTION_COLUMNS)
        sql = f"INSERT OR IGNORE INTO mentions ({','.join(MENTION_COLUMNS)}) VALUES ({placeholders})"
        values = [tuple(row.get(c) for c in MENTION_COLUMNS) for row in rows]
        with self._lock:
            before = self._conn.total_changes
            self._conn.executemany(sql, values)
            self._conn.commit()
            return self._conn.total_changes - before

    def existing_ids(self, ids: list[str]) -> set[str]:
        if not ids:
            return set()
        found: set[str] = set()
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            marks = ",".join("?" for _ in chunk)
            rows = self.query(f"SELECT id FROM mentions WHERE id IN ({marks})", chunk)
            found.update(r["id"] for r in rows)
        return found

    def count_mentions(self) -> int:
        return int(self.scalar("SELECT COUNT(*) FROM mentions") or 0)

    # ---- settings -------------------------------------------------------
    def get_setting(self, key: str, default=None):
        value = self.scalar("SELECT value FROM settings WHERE key = ?", (key,))
        return json.loads(value) if value is not None else default

    def set_setting(self, key: str, value) -> None:
        self.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )


def decode_mention(row: dict) -> dict:
    """Convert a DB row into the JSON shape used by the API."""
    out = dict(row)
    out["aspects"] = json.loads(row["aspects"]) if row.get("aspects") else []
    out["probs"] = json.loads(row["probs"]) if row.get("probs") else {}
    out["is_spam"] = bool(row.get("is_spam"))
    out.pop("keywords", None)
    return out
