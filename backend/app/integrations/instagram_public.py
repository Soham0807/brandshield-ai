"""Monitor ANY public Instagram page - no Instagram account or login needed.

Instagram has no official API for reading other people's pages, so the public
data is fetched through Apify (https://apify.com), a hosted scraping service:

* ``apify/instagram-profile-scraper``  - profile + the latest posts
* ``apify/instagram-comment-scraper``  - comments on those posts

Only one Apify API token is needed (``APIFY_TOKEN`` in backend/.env). Comments
are fetched only for posts whose comment count changed since the last sync, and
are pushed into the normal NLP streaming pipeline like every other source.
"""

import logging
import re

import httpx

from app.config import Settings
from app.db import Database, parse_any_datetime, to_iso, utcnow

logger = logging.getLogger("brandshield.instagram_public")

USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")
URL_USERNAME_RE = re.compile(r"instagram\.com/([A-Za-z0-9._]{1,30})/?", re.I)
SHORTCODE_RE = re.compile(r"instagram\.com/(?:[A-Za-z0-9._]+/)?(?:p|reel|tv)/([A-Za-z0-9_-]+)", re.I)
RESERVED = {"p", "reel", "reels", "tv", "explore", "stories", "accounts"}


class InstagramPublicError(Exception):
    """Message that can be shown to the user."""


def normalise_username(query: str) -> str:
    """Accept @handle, handle or a profile URL."""
    text = (query or "").strip()
    match = URL_USERNAME_RE.search(text)
    if match and match.group(1).lower() not in RESERVED:
        text = match.group(1)
    text = text.lstrip("@").strip().strip("/").lower()
    if not USERNAME_RE.match(text):
        raise InstagramPublicError("Enter an Instagram handle such as @zomato or a link to the profile.")
    return text


def shortcode(url: str | None) -> str | None:
    match = SHORTCODE_RE.search(url or "")
    return match.group(1) if match else None


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class InstagramPublicService:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.apify_token)

    # ------------------------------------------------------------------
    # Apify
    # ------------------------------------------------------------------
    async def _run(self, client: httpx.AsyncClient, actor: str, payload: dict) -> list[dict]:
        if not self.configured:
            raise InstagramPublicError("Monitoring public Instagram pages isn't switched on (APIFY_TOKEN is missing).")
        url = f"{self.settings.apify_base.rstrip('/')}/acts/{actor}/run-sync-get-dataset-items"
        try:
            resp = await client.post(url, json=payload, headers={"Authorization": f"Bearer {self.settings.apify_token}"})
        except httpx.TimeoutException as exc:
            raise InstagramPublicError("Instagram took too long to answer. Try again in a minute.") from exc
        if resp.status_code in (401, 403):
            raise InstagramPublicError("The Apify token was rejected. Check APIFY_TOKEN in backend/.env.")
        if resp.status_code == 402:
            raise InstagramPublicError("The Apify account has run out of free credit for this month.")
        if resp.status_code >= 400:
            try:
                message = resp.json().get("error", {}).get("message") or resp.text[:200]
            except ValueError:
                message = resp.text[:200]
            raise InstagramPublicError(f"Could not read Instagram right now ({resp.status_code}): {message}")
        data = resp.json()
        return data if isinstance(data, list) else []

    async def fetch_profile(self, client: httpx.AsyncClient, username: str) -> dict:
        items = await self._run(client, "apify~instagram-profile-scraper",
                                {"usernames": [username], "resultsLimit": self.settings.instagram_pages_posts})
        profile = next((i for i in items if (i.get("username") or "").lower() == username), None)
        if not profile or profile.get("error"):
            raise InstagramPublicError(f"No public Instagram page found for @{username}.")
        if profile.get("private"):
            raise InstagramPublicError(f"@{username} is a private account - only public pages can be monitored.")
        return profile

    async def fetch_comments(self, client: httpx.AsyncClient, post_urls: list[str]) -> list[dict]:
        if not post_urls:
            return []
        return await self._run(client, "apify~instagram-comment-scraper",
                               {"directUrls": post_urls, "resultsLimit": self.settings.instagram_pages_comments_per_post})

    # ------------------------------------------------------------------
    # pages
    # ------------------------------------------------------------------
    def save_page(self, profile: dict) -> dict:
        username = profile["username"].lower()
        self.db.execute(
            "INSERT INTO ig_pages (username, full_name, biography, profile_pic_url, followers_count, follows_count, "
            "posts_count, verified, category, added_at, last_error) VALUES (?,?,?,?,?,?,?,?,?,?,NULL) "
            "ON CONFLICT(username) DO UPDATE SET full_name=excluded.full_name, biography=excluded.biography, "
            "profile_pic_url=excluded.profile_pic_url, followers_count=excluded.followers_count, "
            "follows_count=excluded.follows_count, posts_count=excluded.posts_count, verified=excluded.verified, "
            "category=excluded.category",
            (username, profile.get("fullName"), (profile.get("biography") or "")[:500],
             profile.get("profilePicUrlHD") or profile.get("profilePicUrl"), _int(profile.get("followersCount")),
             _int(profile.get("followsCount")), _int(profile.get("postsCount")), int(bool(profile.get("verified"))),
             profile.get("businessCategoryName"), to_iso(utcnow())),
        )
        return self.get_page(username)

    def list_pages(self) -> list[dict]:
        rows = self.db.query("SELECT * FROM ig_pages ORDER BY added_at")
        for row in rows:
            row.update(self.db.query(
                "SELECT COUNT(*) AS analysed_comments, "
                "SUM(sentiment='positive' AND is_spam=0) AS positive, "
                "SUM(sentiment='neutral' AND is_spam=0) AS neutral, "
                "SUM(sentiment='negative' AND is_spam=0) AS negative, SUM(is_spam) AS spam "
                "FROM mentions WHERE source='instagram' AND parent_id IN "
                "(SELECT id FROM ig_page_posts WHERE username = ?)", (row["username"],))[0])
            row["posts_tracked"] = self.db.scalar("SELECT COUNT(*) FROM ig_page_posts WHERE username = ?",
                                                  (row["username"],))
            row["verified"] = bool(row.get("verified"))
        return rows

    def get_page(self, username: str) -> dict | None:
        return next((p for p in self.list_pages() if p["username"] == username), None)

    def remove_page(self, username: str, delete_data: bool) -> bool:
        if not self.db.scalar("SELECT 1 FROM ig_pages WHERE username = ?", (username,)):
            return False
        if delete_data:
            self.db.execute("DELETE FROM mentions WHERE source='instagram' AND parent_id IN "
                            "(SELECT id FROM ig_page_posts WHERE username = ?)", (username,))
        self.db.execute("DELETE FROM ig_page_posts WHERE username = ?", (username,))
        self.db.execute("DELETE FROM ig_pages WHERE username = ?", (username,))
        return True

    def posts(self, username: str | None, limit: int = 60) -> list[dict]:
        """Same field names as the official-API media list, so the UI can reuse its cards."""
        where, params = ("WHERE p.username = ?", [username]) if username else ("", [])
        return self.db.query(
            "SELECT p.id, p.username, p.caption, p.media_type, p.display_url AS media_url, "
            "p.display_url AS thumbnail_url, p.permalink, p.timestamp, p.like_count, p.comments_count, "
            "(SELECT COUNT(*) FROM mentions x WHERE x.parent_id = p.id AND x.is_spam = 0) AS analysed, "
            "(SELECT COUNT(*) FROM mentions x WHERE x.parent_id = p.id AND x.is_spam = 0 AND x.sentiment='positive') AS positive, "
            "(SELECT COUNT(*) FROM mentions x WHERE x.parent_id = p.id AND x.is_spam = 0 AND x.sentiment='neutral') AS neutral, "
            "(SELECT COUNT(*) FROM mentions x WHERE x.parent_id = p.id AND x.is_spam = 0 AND x.sentiment='negative') AS negative, "
            "(SELECT COUNT(*) FROM mentions x WHERE x.parent_id = p.id AND x.is_spam = 1) AS spam, "
            "(SELECT AVG(score) FROM mentions x WHERE x.parent_id = p.id AND x.is_spam = 0) AS avg_score "
            f"FROM ig_page_posts p {where} ORDER BY p.timestamp DESC LIMIT ?", params + [limit])

    # ------------------------------------------------------------------
    # syncing
    # ------------------------------------------------------------------
    async def sync_page(self, username: str, force: bool = False) -> list[dict]:
        """Refresh the profile + latest posts, then fetch comments of posts that changed."""
        async with httpx.AsyncClient(timeout=self.settings.apify_timeout_seconds) as client:
            profile = await self.fetch_profile(client, username)
            self.save_page(profile)
            known = {r["id"]: r for r in self.db.query(
                "SELECT id, comments_count, synced_comments FROM ig_page_posts WHERE username = ?", (username,))}
            now = to_iso(utcnow())
            to_fetch: dict[str, str] = {}   # shortcode -> post id
            for post in (profile.get("latestPosts") or [])[: self.settings.instagram_pages_posts]:
                code = post.get("shortCode") or shortcode(post.get("url"))
                if not code:
                    continue
                post_id = f"igp_{code}"
                count = _int(post.get("commentsCount"))
                previous = known.get(post_id)
                changed = force or previous is None or previous["synced_comments"] != count
                if count and changed and not post.get("isCommentsDisabled"):
                    to_fetch[code] = post_id
                self.db.execute(
                    "INSERT INTO ig_page_posts (id, username, shortcode, caption, media_type, display_url, permalink, "
                    "timestamp, like_count, comments_count, synced_comments, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET caption=excluded.caption, display_url=excluded.display_url, "
                    "like_count=excluded.like_count, comments_count=excluded.comments_count, updated_at=excluded.updated_at",
                    (post_id, username, code, (post.get("caption") or "")[:2000], (post.get("type") or "").upper(),
                     post.get("displayUrl"), post.get("url") or f"https://www.instagram.com/p/{code}/",
                     to_iso(parse_any_datetime(post.get("timestamp"))), _int(post.get("likesCount")), count,
                     (previous or {}).get("synced_comments", 0), now),
                )

            raws: list[dict] = []
            fetched: dict[str, int] = {}
            comments = await self.fetch_comments(
                client, [f"https://www.instagram.com/p/{code}/" for code in to_fetch])
            for c in comments:
                code = shortcode(c.get("postUrl")) or shortcode(c.get("commentUrl"))
                post_id = to_fetch.get(code) if code else None
                text = (c.get("text") or "").strip()
                # the page's own replies are not customer opinion
                if not post_id or not text or (c.get("ownerUsername") or "").lower() == username:
                    continue
                fetched[post_id] = fetched.get(post_id, 0) + 1
                raws.append({
                    "source": "instagram",
                    "origin": "live",
                    "external_id": str(c.get("id")),
                    "author": c.get("ownerUsername"),
                    "text": text[:2000],
                    "url": c.get("commentUrl") or c.get("postUrl"),
                    "created_at": to_iso(parse_any_datetime(c.get("timestamp"))),
                    "engagement": _int(c.get("likesCount")),
                    "parent_id": post_id,
                })
            # remember the comment count we synced at, so unchanged posts are skipped next time
            for code, post_id in to_fetch.items():
                if fetched.get(post_id):
                    self.db.execute("UPDATE ig_page_posts SET synced_comments = comments_count WHERE id = ?", (post_id,))

        self.db.execute("UPDATE ig_pages SET last_sync_at=?, last_error=NULL WHERE username=?",
                        (to_iso(utcnow()), username))
        logger.info("Instagram @%s: %s posts checked, %s new comments", username, len(to_fetch), len(raws))
        return raws

    async def sync_all(self, force: bool = False) -> list[dict]:
        raws, errors = [], []
        for page in self.db.query("SELECT username FROM ig_pages"):
            try:
                raws.extend(await self.sync_page(page["username"], force))
            except (InstagramPublicError, httpx.HTTPError) as exc:
                message = str(exc) or type(exc).__name__
                errors.append(f"@{page['username']}: {message}")
                self.set_error(page["username"], message)
        if errors and not raws:
            raise InstagramPublicError("; ".join(errors))
        return raws

    def set_error(self, username: str, message: str) -> None:
        self.db.execute("UPDATE ig_pages SET last_error=?, last_sync_at=? WHERE username=?",
                        (message, to_iso(utcnow()), username))


class InstagramPageCollector:
    """Polls every monitored public page, like any other data source."""

    name = "instagram_pages"
    requires_credentials = True

    def __init__(self, service: InstagramPublicService, settings: Settings):
        self.service = service
        self.interval = settings.instagram_pages_poll_seconds
        self.last_poll: float | None = None
        self.last_count = 0
        self.last_error: str | None = None
        self.total = 0

    def configured(self) -> bool:
        return self.service.configured

    def status(self) -> dict:
        return {
            "name": self.name,
            "configured": self.configured(),
            "requires_credentials": self.requires_credentials,
            "pages": self.service.db.scalar("SELECT COUNT(*) FROM ig_pages") or 0,
            "last_poll": self.last_poll,
            "last_count": self.last_count,
            "last_error": self.last_error,
            "total_collected": self.total,
        }

    async def poll(self, brand: str, keywords: list[str]) -> list[dict]:
        if not self.service.db.scalar("SELECT 1 FROM ig_pages LIMIT 1"):
            return []
        return await self.service.sync_all()
