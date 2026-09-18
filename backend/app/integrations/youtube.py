"""YouTube channel monitoring with the official YouTube Data API v3.

The user types a channel handle (``@mkbhd``), a channel URL or a channel id.
BrandShield resolves it, stores the channel, then keeps pulling the channel's
recent uploads and the real comments on them into the NLP pipeline.

Everything here is read-only public data. Quota cost per sync is tiny:
channels.list = 1 unit, playlistItems.list = 1, videos.list = 1,
commentThreads.list = 1 per page — the free 10,000 units/day is plenty.
"""

import logging
import re

import httpx

from app.config import Settings
from app.db import Database, parse_any_datetime, to_iso, utcnow

logger = logging.getLogger("brandshield.youtube")

HANDLE_RE = re.compile(r"(?:youtube\.com/)?@([A-Za-z0-9._-]{3,60})")
CHANNEL_ID_RE = re.compile(r"(UC[A-Za-z0-9_-]{22})")
CUSTOM_URL_RE = re.compile(r"youtube\.com/(?:c/|user/)?([A-Za-z0-9._-]{3,60})")
MAX_COMMENT_PAGES = 5


class YouTubeError(Exception):
    """Message safe to show the user."""


class YouTubeService:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings

    # ------------------------------------------------------------------
    @property
    def configured(self) -> bool:
        return bool(self.settings.youtube_api_key)

    @property
    def api(self) -> str:
        return self.settings.youtube_api_base.rstrip("/")

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict) -> dict:
        if not self.configured:
            raise YouTubeError("No YouTube API key yet — add it on the YouTube page.")
        resp = await client.get(f"{self.api}/{path}",
                                params={**params, "key": self.settings.youtube_api_key})
        if resp.status_code >= 400:
            try:
                error = resp.json()["error"]
                reason = (error.get("errors") or [{}])[0].get("reason", "")
                message = error.get("message", resp.text[:200])
            except Exception:
                reason, message = "", resp.text[:200]
            if reason in ("quotaExceeded", "dailyLimitExceeded"):
                raise YouTubeError("YouTube's daily quota is used up. It resets at 12:30 PM IST.")
            if reason == "commentsDisabled":
                raise _CommentsDisabled()
            if reason in ("keyInvalid", "badRequest") or "API key not valid" in message:
                raise YouTubeError(f"The YouTube API key was rejected: {message}")
            if reason == "accessNotConfigured":
                raise YouTubeError("Enable 'YouTube Data API v3' for this key in Google Cloud Console.")
            raise YouTubeError(f"YouTube API error ({resp.status_code}): {message}")
        return resp.json()

    # ------------------------------------------------------------------
    # channels
    # ------------------------------------------------------------------
    async def resolve(self, query: str) -> dict:
        """Find a channel from a handle, URL, channel id or name."""
        query = (query or "").strip()
        if not query:
            raise YouTubeError("Enter a channel handle, for example @mkbhd")
        part = "snippet,statistics,contentDetails,brandingSettings"

        async with httpx.AsyncClient(timeout=30) as client:
            lookups = []
            if (m := CHANNEL_ID_RE.search(query)):
                lookups.append({"part": part, "id": m.group(1)})
            if (m := HANDLE_RE.search(query)):
                lookups.append({"part": part, "forHandle": f"@{m.group(1)}"})
            elif not query.startswith("http") and " " not in query and not CHANNEL_ID_RE.search(query):
                lookups.append({"part": part, "forHandle": f"@{query.lstrip('@')}"})
            if (m := CUSTOM_URL_RE.search(query)) and "@" not in query:
                lookups.append({"part": part, "forUsername": m.group(1)})

            for params in lookups:
                data = await self._get(client, "channels", params)
                if data.get("items"):
                    return self._channel_row(data["items"][0])

            # last resort: search by name (costs 100 quota units)
            try:
                data = await self._get(client, "search", {
                    "part": "snippet", "type": "channel", "q": query.lstrip("@"), "maxResults": 1})
            except YouTubeError as exc:
                if "quota" in str(exc).lower() or "key" in str(exc).lower():
                    raise
                raise YouTubeError(f"No YouTube channel found for {query!r}. Try the exact handle, e.g. @mkbhd") from exc
            items = data.get("items") or []
            if not items:
                raise YouTubeError(f"No YouTube channel found for {query!r}. Try the exact handle, e.g. @mkbhd")
            channel_id = items[0]["snippet"]["channelId"]
            data = await self._get(client, "channels", {"part": part, "id": channel_id})
            if not data.get("items"):
                raise YouTubeError(f"Could not read the channel {query!r}")
            return self._channel_row(data["items"][0])

    @staticmethod
    def _channel_row(item: dict) -> dict:
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        thumbs = snippet.get("thumbnails", {})
        thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url")
        return {
            "channel_id": item["id"],
            "handle": (snippet.get("customUrl") or "").lstrip("@") or None,
            "title": snippet.get("title"),
            "description": (snippet.get("description") or "")[:800],
            "thumbnail_url": thumb,
            "country": snippet.get("country"),
            "published_at": to_iso(parse_any_datetime(snippet.get("publishedAt"))),
            "subscriber_count": int(stats.get("subscriberCount") or 0),
            "video_count": int(stats.get("videoCount") or 0),
            "view_count": int(stats.get("viewCount") or 0),
            "uploads_playlist": (item.get("contentDetails", {}).get("relatedPlaylists", {}) or {}).get("uploads"),
        }

    def save_channel(self, row: dict) -> dict:
        now = to_iso(utcnow())
        self.db.execute(
            "INSERT INTO youtube_channels (channel_id, handle, title, description, thumbnail_url, country, "
            "published_at, subscriber_count, video_count, view_count, uploads_playlist, added_at, last_error) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NULL) "
            "ON CONFLICT(channel_id) DO UPDATE SET handle=excluded.handle, title=excluded.title, "
            "description=excluded.description, thumbnail_url=excluded.thumbnail_url, "
            "subscriber_count=excluded.subscriber_count, video_count=excluded.video_count, "
            "view_count=excluded.view_count, uploads_playlist=excluded.uploads_playlist, last_error=NULL",
            (row["channel_id"], row["handle"], row["title"], row["description"], row["thumbnail_url"],
             row["country"], row["published_at"], row["subscriber_count"], row["video_count"],
             row["view_count"], row["uploads_playlist"], now),
        )
        return self.get_channel(row["channel_id"])

    def list_channels(self) -> list[dict]:
        rows = self.db.query("SELECT * FROM youtube_channels ORDER BY added_at")
        for row in rows:
            row.update(self.db.query(
                "SELECT COUNT(*) AS analysed_comments, "
                "SUM(sentiment='positive' AND is_spam=0) AS positive, "
                "SUM(sentiment='neutral' AND is_spam=0) AS neutral, "
                "SUM(sentiment='negative' AND is_spam=0) AS negative, SUM(is_spam) AS spam "
                "FROM mentions WHERE source='youtube' AND parent_id IN "
                "(SELECT id FROM youtube_videos WHERE channel_id = ?)", (row["channel_id"],))[0])
            row["videos_tracked"] = self.db.scalar(
                "SELECT COUNT(*) FROM youtube_videos WHERE channel_id = ?", (row["channel_id"],))
        return rows

    def get_channel(self, channel_id: str) -> dict | None:
        return next((c for c in self.list_channels() if c["channel_id"] == channel_id), None)

    def remove_channel(self, channel_id: str, delete_data: bool) -> bool:
        if not self.db.scalar("SELECT 1 FROM youtube_channels WHERE channel_id = ?", (channel_id,)):
            return False
        if delete_data:
            self.db.execute("DELETE FROM mentions WHERE source='youtube' AND parent_id IN "
                            "(SELECT id FROM youtube_videos WHERE channel_id = ?)", (channel_id,))
        self.db.execute("DELETE FROM youtube_videos WHERE channel_id = ?", (channel_id,))
        self.db.execute("DELETE FROM youtube_channels WHERE channel_id = ?", (channel_id,))
        return True

    def videos(self, channel_id: str | None = None, limit: int = 60) -> list[dict]:
        where, params = ("WHERE v.channel_id = ?", [channel_id]) if channel_id else ("", [])
        return self.db.query(
            "SELECT v.*, c.title AS channel_title, c.handle, "
            "(SELECT COUNT(*) FROM mentions m WHERE m.parent_id = v.id AND m.is_spam = 0) AS analysed, "
            "(SELECT COUNT(*) FROM mentions m WHERE m.parent_id = v.id AND m.is_spam = 0 AND m.sentiment='positive') AS positive, "
            "(SELECT COUNT(*) FROM mentions m WHERE m.parent_id = v.id AND m.is_spam = 0 AND m.sentiment='neutral') AS neutral, "
            "(SELECT COUNT(*) FROM mentions m WHERE m.parent_id = v.id AND m.is_spam = 0 AND m.sentiment='negative') AS negative, "
            "(SELECT COUNT(*) FROM mentions m WHERE m.parent_id = v.id AND m.is_spam = 1) AS spam, "
            "(SELECT AVG(score) FROM mentions m WHERE m.parent_id = v.id AND m.is_spam = 0) AS avg_score "
            f"FROM youtube_videos v JOIN youtube_channels c ON c.channel_id = v.channel_id {where} "
            "ORDER BY v.published_at DESC LIMIT ?", params + [limit])

    # ------------------------------------------------------------------
    # syncing
    # ------------------------------------------------------------------
    async def sync_channel(self, channel: dict, force: bool = False) -> list[dict]:
        """Refresh channel stats, recent videos and their comments."""
        raws: list[dict] = []
        max_videos = self.settings.youtube_max_videos
        async with httpx.AsyncClient(timeout=40) as client:
            fresh = await self._get(client, "channels", {
                "part": "snippet,statistics,contentDetails", "id": channel["channel_id"]})
            if not fresh.get("items"):
                raise YouTubeError("The channel is no longer available on YouTube.")
            info = self._channel_row(fresh["items"][0])
            playlist = info["uploads_playlist"] or channel.get("uploads_playlist")
            if not playlist:
                raise YouTubeError("This channel has no public uploads playlist.")

            # recent uploads (1 unit per page of 50)
            video_ids: list[str] = []
            page_token = None
            while len(video_ids) < max_videos:
                params = {"part": "contentDetails", "playlistId": playlist,
                          "maxResults": min(50, max_videos - len(video_ids))}
                if page_token:
                    params["pageToken"] = page_token
                data = await self._get(client, "playlistItems", params)
                video_ids += [i["contentDetails"]["videoId"] for i in data.get("items", [])
                              if i.get("contentDetails", {}).get("videoId")]
                page_token = data.get("nextPageToken")
                if not page_token:
                    break

            known = {r["id"]: r for r in self.db.query(
                "SELECT id, comment_count, synced_comments FROM youtube_videos WHERE channel_id = ?",
                (channel["channel_id"],))}
            now = to_iso(utcnow())

            # stats for up to 50 videos per call
            for chunk_start in range(0, len(video_ids), 50):
                chunk = video_ids[chunk_start:chunk_start + 50]
                data = await self._get(client, "videos", {"part": "snippet,statistics", "id": ",".join(chunk)})
                for item in data.get("items", []):
                    snippet = item.get("snippet", {})
                    stats = item.get("statistics", {})
                    thumbs = snippet.get("thumbnails", {})
                    thumb = (thumbs.get("medium") or thumbs.get("high") or thumbs.get("default") or {}).get("url")
                    comment_count = int(stats.get("commentCount") or 0)
                    previous = known.get(item["id"])
                    changed = force or previous is None or previous["synced_comments"] != comment_count

                    fetched = 0
                    if comment_count and changed:
                        try:
                            comments = await self._video_comments(client, item["id"])
                            fetched = len(comments)
                            raws.extend(comments)
                        except _CommentsDisabled:
                            comment_count = 0

                    self.db.execute(
                        "INSERT INTO youtube_videos (id, channel_id, title, description, thumbnail_url, "
                        "published_at, view_count, like_count, comment_count, synced_comments, updated_at) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title, "
                        "thumbnail_url=excluded.thumbnail_url, view_count=excluded.view_count, "
                        "like_count=excluded.like_count, comment_count=excluded.comment_count, "
                        "synced_comments=excluded.synced_comments, updated_at=excluded.updated_at",
                        (item["id"], channel["channel_id"], snippet.get("title"),
                         (snippet.get("description") or "")[:500], thumb,
                         to_iso(parse_any_datetime(snippet.get("publishedAt"))),
                         int(stats.get("viewCount") or 0), int(stats.get("likeCount") or 0),
                         comment_count,
                         # remember the count we synced at; 0 when nothing came back so we retry later
                         (comment_count if fetched else 0) if changed else (previous or {}).get("synced_comments", 0),
                         now),
                    )

        self.db.execute(
            "UPDATE youtube_channels SET title=?, handle=?, thumbnail_url=?, subscriber_count=?, video_count=?, "
            "view_count=?, uploads_playlist=?, last_sync_at=?, last_error=NULL WHERE channel_id=?",
            (info["title"], info["handle"], info["thumbnail_url"], info["subscriber_count"], info["video_count"],
             info["view_count"], playlist, to_iso(utcnow()), channel["channel_id"]))
        logger.info("YouTube: synced %s — %s new comments", info["title"], len(raws))
        return raws

    async def _video_comments(self, client: httpx.AsyncClient, video_id: str) -> list[dict]:
        items: list[dict] = []
        page_token = None
        for _ in range(MAX_COMMENT_PAGES):
            params = {"part": "snippet,replies", "videoId": video_id, "order": "time",
                      "maxResults": 100, "textFormat": "plainText"}
            if page_token:
                params["pageToken"] = page_token
            data = await self._get(client, "commentThreads", params)
            for thread in data.get("items", []):
                top = thread.get("snippet", {}).get("topLevelComment", {})
                for comment in [top] + (thread.get("replies", {}).get("comments") or []):
                    snippet = comment.get("snippet", {})
                    text = (snippet.get("textOriginal") or snippet.get("textDisplay") or "").strip()
                    if not text:
                        continue
                    items.append({
                        "source": "youtube",
                        "origin": "live",
                        "external_id": comment.get("id"),
                        "author": snippet.get("authorDisplayName"),
                        "text": text[:2000],
                        "url": f"https://www.youtube.com/watch?v={video_id}&lc={comment.get('id')}",
                        "created_at": snippet.get("publishedAt"),
                        "engagement": int(snippet.get("likeCount") or 0),
                        "parent_id": video_id,
                    })
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return items

    async def sync_all(self, force: bool = False) -> list[dict]:
        raws, errors = [], []
        for channel in self.db.query("SELECT * FROM youtube_channels"):
            try:
                raws.extend(await self.sync_channel(channel, force))
            except (YouTubeError, httpx.HTTPError) as exc:
                message = str(exc) or type(exc).__name__
                errors.append(f"{channel['title']}: {message}")
                self.db.execute("UPDATE youtube_channels SET last_error=?, last_sync_at=? WHERE channel_id=?",
                                (message, to_iso(utcnow()), channel["channel_id"]))
        if errors and not raws:
            raise YouTubeError("; ".join(errors))
        return raws


class _CommentsDisabled(Exception):
    """The video has comments switched off."""


class YouTubeChannelCollector:
    """Polls every channel the user added, like any other data source."""

    name = "youtube"
    requires_credentials = True

    def __init__(self, service: YouTubeService, settings: Settings):
        self.service = service
        self.settings = settings
        self.interval = settings.youtube_poll_seconds
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
            "channels": self.service.db.scalar("SELECT COUNT(*) FROM youtube_channels") or 0,
            "last_poll": self.last_poll,
            "last_count": self.last_count,
            "last_error": self.last_error,
            "total_collected": self.total,
        }

    async def poll(self, brand: str, keywords: list[str]) -> list[dict]:
        if not self.service.db.scalar("SELECT 1 FROM youtube_channels LIMIT 1"):
            return []
        return await self.service.sync_all()
