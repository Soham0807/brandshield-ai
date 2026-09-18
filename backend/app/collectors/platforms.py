"""Connectors for real platforms. Each ``poll`` returns raw mention dicts.

* Reddit      - OAuth app credentials if configured, otherwise public search JSON
* RSS / News  - Google News RSS search for the brand + any custom feeds
* Twitter / X - API v2 recent search (requires a bearer token)
* Instagram   - see app/integrations/instagram.py (OAuth login)
"""

import html
import logging
import re
import time

import feedparser
import httpx

logger = logging.getLogger("brandshield.collectors")
TAG_RE = re.compile(r"<[^>]+>")


class CollectorError(Exception):
    pass


class BaseCollector:
    name = "base"

    def __init__(self, settings):
        self.settings = settings
        self.last_poll: float | None = None
        self.last_count = 0
        self.last_error: str | None = None
        self.total = 0

    requires_credentials = True

    def configured(self) -> bool:
        return False

    def status(self) -> dict:
        return {
            "name": self.name,
            "configured": self.configured(),
            "requires_credentials": self.requires_credentials,
            "last_poll": self.last_poll,
            "last_count": self.last_count,
            "last_error": self.last_error,
            "total_collected": self.total,
        }

    async def poll(self, brand: str, keywords: list[str]) -> list[dict]:
        raise NotImplementedError


class RedditCollector(BaseCollector):
    name = "reddit"
    requires_credentials = True  # Reddit blocks most unauthenticated API traffic (HTTP 403)

    def configured(self) -> bool:
        return bool(self.settings.reddit_client_id and self.settings.reddit_client_secret)

    def __init__(self, settings):
        super().__init__(settings)
        self._token: str | None = None
        self._token_expiry = 0.0

    async def _auth_headers(self, client: httpx.AsyncClient) -> dict:
        headers = {"User-Agent": self.settings.reddit_user_agent}
        if not (self.settings.reddit_client_id and self.settings.reddit_client_secret):
            return headers
        if not self._token or time.time() > self._token_expiry:
            resp = await client.post(
                "https://www.reddit.com/api/v1/access_token",
                data={"grant_type": "client_credentials"},
                auth=(self.settings.reddit_client_id, self.settings.reddit_client_secret),
                headers=headers,
            )
            resp.raise_for_status()
            payload = resp.json()
            self._token = payload["access_token"]
            self._token_expiry = time.time() + payload.get("expires_in", 3600) - 60
        headers["Authorization"] = f"bearer {self._token}"
        return headers

    async def poll(self, brand, keywords):
        query = " OR ".join(f'"{k}"' for k in ([brand] + keywords)[:5])
        async with httpx.AsyncClient(timeout=20) as client:
            headers = await self._auth_headers(client)
            url = ("https://oauth.reddit.com/search" if "Authorization" in headers
                   else "https://www.reddit.com/search.json")
            resp = await client.get(url,
                                    params={"q": query, "sort": "new", "limit": 50, "raw_json": 1},
                                    headers=headers)
            if resp.status_code in (401, 403, 429):
                raise CollectorError(f"Reddit returned HTTP {resp.status_code}. Add REDDIT_CLIENT_ID/SECRET in .env")
            resp.raise_for_status()
            children = resp.json().get("data", {}).get("children", [])
        items = []
        for child in children:
            d = child.get("data", {})
            text = f"{d.get('title', '')}. {d.get('selftext', '')}".strip(" .")
            if not text:
                continue
            items.append({
                "source": "reddit",
                "external_id": d.get("id"),
                "author": d.get("author"),
                "text": text[:2000],
                "url": f"https://www.reddit.com{d.get('permalink', '')}",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(d.get("created_utc", time.time()))),
                "engagement": int(d.get("score", 0)) + int(d.get("num_comments", 0)),
            })
        return items


class RssCollector(BaseCollector):
    name = "rss"
    requires_credentials = False

    def configured(self) -> bool:
        return True

    def feeds(self, brand, keywords) -> list[str]:
        query = httpx.QueryParams({"q": f'"{brand}"', "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
        urls = [f"https://news.google.com/rss/search?{query}"]
        urls += [u.strip() for u in self.settings.rss_feeds.split(",") if u.strip()]
        return urls

    async def poll(self, brand, keywords):
        terms = [t.lower() for t in [brand] + keywords]
        items = []
        async with httpx.AsyncClient(timeout=20, follow_redirects=True,
                                     headers={"User-Agent": "Mozilla/5.0 BrandShieldAI"}) as client:
            for i, url in enumerate(self.feeds(brand, keywords)):
                resp = await client.get(url)
                resp.raise_for_status()
                parsed = feedparser.parse(resp.content)
                for entry in parsed.entries[:50]:
                    title = html.unescape(TAG_RE.sub(" ", entry.get("title", "")))
                    summary = html.unescape(TAG_RE.sub(" ", entry.get("summary", "")))
                    text = f"{title}. {summary}" if summary and summary not in title else title
                    # custom feeds are filtered by keyword, the Google News search is already filtered
                    if i > 0 and not any(t in text.lower() for t in terms):
                        continue
                    published = entry.get("published_parsed") or entry.get("updated_parsed")
                    items.append({
                        "source": "news",
                        "external_id": entry.get("id") or entry.get("link"),
                        "author": entry.get("source", {}).get("title") if isinstance(entry.get("source"), dict) else None,
                        "text": " ".join(text.split())[:2000],
                        "url": entry.get("link"),
                        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", published) if published else None,
                        "engagement": 0,
                    })
        return items


class TwitterCollector(BaseCollector):
    name = "twitter"

    def __init__(self, settings):
        super().__init__(settings)
        self.since_id: str | None = None

    def configured(self) -> bool:
        return bool(self.settings.twitter_bearer_token)

    async def poll(self, brand, keywords):
        if not self.configured():
            raise CollectorError("TWITTER_BEARER_TOKEN is not set in backend/.env")
        terms = " OR ".join(f'"{k}"' for k in ([brand] + keywords)[:6])
        params = {
            "query": f"({terms}) -is:retweet",
            "max_results": 50,
            "tweet.fields": "created_at,public_metrics,lang,author_id",
            "expansions": "author_id",
            "user.fields": "username",
        }
        if self.since_id:
            params["since_id"] = self.since_id
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get("https://api.twitter.com/2/tweets/search/recent", params=params,
                                    headers={"Authorization": f"Bearer {self.settings.twitter_bearer_token}"})
        if resp.status_code == 429:
            raise CollectorError("Twitter rate limit reached")
        if resp.status_code >= 400:
            raise CollectorError(f"Twitter API error {resp.status_code}: {resp.text[:200]}")
        payload = resp.json()
        users = {u["id"]: u["username"] for u in payload.get("includes", {}).get("users", [])}
        tweets = payload.get("data", [])
        if payload.get("meta", {}).get("newest_id"):
            self.since_id = payload["meta"]["newest_id"]
        items = []
        for tw in tweets:
            m = tw.get("public_metrics", {})
            username = users.get(tw.get("author_id"), tw.get("author_id"))
            items.append({
                "source": "twitter",
                "external_id": tw["id"],
                "author": username,
                "text": tw.get("text", ""),
                "url": f"https://x.com/{username}/status/{tw['id']}",
                "created_at": tw.get("created_at"),
                "engagement": m.get("like_count", 0) + m.get("retweet_count", 0) + m.get("reply_count", 0),
            })
        return items
