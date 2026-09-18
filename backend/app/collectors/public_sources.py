"""Read-only collectors for brands you do NOT own.

* YouTube   - comments on videos about the brand (official Data API v3, free key)
* App Store - customer reviews of the brand's iOS app (public RSS, no key)

Both only read public data and never post anything. Star ratings from the App
Store are kept as ``true_label``, which gives a free accuracy check of the
sentiment model against real human ratings.
"""

import logging
import time

import httpx

from app.collectors.platforms import BaseCollector, CollectorError

logger = logging.getLogger("brandshield.collectors")

RATING_TO_LABEL = {1: "negative", 2: "negative", 3: "neutral", 4: "positive", 5: "positive"}


class YouTubeCollector(BaseCollector):
    """Comments on recent videos that mention the brand."""

    name = "youtube"
    requires_credentials = True

    def __init__(self, settings):
        super().__init__(settings)
        self._videos: list[dict] = []
        self._videos_fetched_at = 0.0
        self._videos_query: str | None = None

    def configured(self) -> bool:
        return bool(self.settings.youtube_api_key)

    @property
    def api(self) -> str:
        return self.settings.youtube_api_base.rstrip("/")

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict) -> dict:
        resp = await client.get(f"{self.api}/{path}", params={**params, "key": self.settings.youtube_api_key})
        if resp.status_code >= 400:
            try:
                error = resp.json()["error"]
                reason = (error.get("errors") or [{}])[0].get("reason", "")
                message = error.get("message", resp.text[:200])
            except Exception:
                reason, message = "", resp.text[:200]
            if reason in ("quotaExceeded", "dailyLimitExceeded"):
                raise CollectorError("YouTube daily quota is used up - it resets at midnight Pacific time.")
            if reason in ("commentsDisabled", "videoNotFound", "forbidden"):
                raise _SkipVideo(reason)
            if resp.status_code in (400, 403) and "API key" in message:
                raise CollectorError(f"YouTube rejected the API key: {message}")
            raise CollectorError(f"YouTube API error ({resp.status_code}): {message}")
        return resp.json()

    async def _refresh_videos(self, client: httpx.AsyncClient, query: str) -> None:
        """Search costs 100 quota units, so the video list is cached for hours."""
        fresh = time.time() - self._videos_fetched_at < self.settings.youtube_search_interval_hours * 3600
        if self._videos and fresh and self._videos_query == query:
            return
        data = await self._get(client, "search", {
            "part": "snippet", "q": query, "type": "video", "order": "date",
            "maxResults": self.settings.youtube_max_videos, "relevanceLanguage": "en",
        })
        self._videos = [{
            "id": item["id"]["videoId"],
            "title": item["snippet"]["title"],
            "channel": item["snippet"]["channelTitle"],
        } for item in data.get("items", []) if item.get("id", {}).get("videoId")]
        self._videos_fetched_at = time.time()
        self._videos_query = query
        logger.info("YouTube: tracking %s videos for %r", len(self._videos), query)

    async def poll(self, brand, keywords):
        if not self.configured():
            raise CollectorError("YOUTUBE_API_KEY is not set - add it in Settings → API keys")
        items: list[dict] = []
        async with httpx.AsyncClient(timeout=30) as client:
            await self._refresh_videos(client, brand)
            for video in self._videos:
                try:
                    items.extend(await self._video_comments(client, video))
                except _SkipVideo:
                    continue
        return items

    async def _video_comments(self, client: httpx.AsyncClient, video: dict) -> list[dict]:
        items: list[dict] = []
        page_token = None
        for _ in range(self.settings.youtube_comment_pages):
            params = {"part": "snippet,replies", "videoId": video["id"], "order": "time",
                      "maxResults": 100, "textFormat": "plainText"}
            if page_token:
                params["pageToken"] = page_token
            data = await self._get(client, "commentThreads", params)
            for thread in data.get("items", []):
                top = thread.get("snippet", {}).get("topLevelComment", {})
                comments = [top] + (thread.get("replies", {}).get("comments") or [])
                for comment in comments:
                    snippet = comment.get("snippet", {})
                    text = (snippet.get("textOriginal") or snippet.get("textDisplay") or "").strip()
                    if not text:
                        continue
                    items.append({
                        "source": "youtube",
                        "external_id": comment.get("id"),
                        "author": snippet.get("authorDisplayName"),
                        "text": text[:2000],
                        "url": f"https://www.youtube.com/watch?v={video['id']}&lc={comment.get('id')}",
                        "created_at": snippet.get("publishedAt"),
                        "engagement": int(snippet.get("likeCount") or 0),
                    })
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return items


class _SkipVideo(Exception):
    """Comments are disabled or the video disappeared."""


class AppStoreCollector(BaseCollector):
    """Customer reviews of the brand's iOS app (public RSS feed, no API key)."""

    name = "appstore"
    requires_credentials = False

    def __init__(self, settings):
        super().__init__(settings)
        self._app: dict | None = None
        self._app_query: str | None = None

    def configured(self) -> bool:
        return True

    @property
    def country(self) -> str:
        return (self.settings.appstore_country or "in").lower()

    async def _resolve_app(self, client: httpx.AsyncClient, brand: str) -> dict:
        if self.settings.appstore_app_id:
            return {"id": self.settings.appstore_app_id, "name": brand}
        if self._app and self._app_query == brand:
            return self._app
        resp = await client.get("https://itunes.apple.com/search", params={
            "term": brand, "entity": "software", "country": self.country, "limit": 1})
        resp.raise_for_status()
        results = resp.json().get("results") or []
        if not results:
            raise CollectorError(f"No iOS app found for {brand!r} in the {self.country.upper()} App Store. "
                                 "Set APPSTORE_APP_ID in backend/.env to pick one manually.")
        app = {"id": str(results[0]["trackId"]), "name": results[0]["trackName"]}
        self._app, self._app_query = app, brand
        logger.info("App Store: monitoring %s (id %s)", app["name"], app["id"])
        return app

    async def poll(self, brand, keywords):
        items: list[dict] = []
        async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "BrandShieldAI/1.0"}) as client:
            app = await self._resolve_app(client, brand)
            for page in range(1, self.settings.appstore_pages + 1):
                url = (f"https://itunes.apple.com/{self.country}/rss/customerreviews/page={page}"
                       f"/id={app['id']}/sortby=mostrecent/json")
                resp = await client.get(url)
                if resp.status_code == 404:
                    break
                if resp.status_code >= 400:
                    raise CollectorError(f"App Store returned HTTP {resp.status_code}")
                entries = (resp.json().get("feed") or {}).get("entry") or []
                if isinstance(entries, dict):
                    entries = [entries]
                for entry in entries:
                    if "im:rating" not in entry:      # the first entry describes the app itself
                        continue
                    title = entry.get("title", {}).get("label", "")
                    content = entry.get("content", {}).get("label", "")
                    text = f"{title}. {content}".strip(" .") if title not in content else content
                    if not text:
                        continue
                    rating = int(entry["im:rating"]["label"])
                    items.append({
                        "source": "appstore",
                        "external_id": entry.get("id", {}).get("label"),
                        "author": entry.get("author", {}).get("name", {}).get("label"),
                        "text": text[:2000],
                        "url": entry.get("link", {}).get("attributes", {}).get("href"),
                        "created_at": entry.get("updated", {}).get("label"),
                        "engagement": int(entry.get("im:voteCount", {}).get("label") or 0),
                        # the star rating is the reviewer's own verdict: useful ground truth
                        "true_label": RATING_TO_LABEL.get(rating),
                    })
                if len(entries) < 2:
                    break
        return items
