"""Instagram integration using the official "Instagram API with Instagram Login".

Flow (OAuth 2.0 authorization code):

1. The user clicks "Connect Instagram" -> ``/api/auth/instagram/login`` redirects
   the browser to instagram.com, where the user logs in *on Instagram's own page*
   and approves the requested permissions. BrandShield never sees the password.
2. Instagram redirects back to ``/api/auth/instagram/callback?code=...&state=...``.
3. The code is exchanged for a short-lived token, then for a 60-day long-lived
   token, which is stored encrypted and refreshed automatically.
4. Every few minutes the account's recent posts and their comments are pulled
   from the Graph API and pushed into the normal NLP streaming pipeline.

Requirements: an Instagram Professional (Business or Creator) account and a Meta
app with the Instagram product. See README "Connect a real Instagram account".
"""

import logging
import secrets
import threading
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings
from app.db import Database, from_iso, parse_any_datetime, to_iso, utcnow

logger = logging.getLogger("brandshield.instagram")

SCOPES = ["instagram_business_basic", "instagram_business_manage_comments"]
PROFILE_FIELDS = "user_id,username,name,account_type,profile_picture_url,followers_count,follows_count,media_count"
MEDIA_FIELDS = "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,like_count,comments_count"
COMMENT_FIELDS = "id,text,timestamp,username,like_count,replies{id,text,timestamp,username,like_count}"
STATE_TTL_SECONDS = 600
REFRESH_WHEN_DAYS_LEFT = 10
MAX_COMMENT_PAGES = 10


class InstagramError(Exception):
    """An error that can be shown to the user."""


class TokenCipher:
    """Encrypts access tokens at rest with a Fernet key."""

    def __init__(self, settings: Settings):
        key = settings.secret_key.strip()
        if not key:
            key_file = Path(settings.database_path).parent / "secret.key"
            key_file.parent.mkdir(parents=True, exist_ok=True)
            if not key_file.exists():
                key_file.write_text(Fernet.generate_key().decode(), encoding="utf-8")
            key = key_file.read_text(encoding="utf-8").strip()
        self._fernet = Fernet(key.encode())

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise InstagramError("Stored token cannot be decrypted (secret key changed). Reconnect the account.") from exc


def _graph_error(resp: httpx.Response) -> str:
    try:
        err = resp.json().get("error", {})
        if isinstance(err, dict):
            message = err.get("message") or resp.text[:200]
            code = err.get("code")
            return f"{message} (code {code})" if code else message
        return str(err)
    except ValueError:
        return f"HTTP {resp.status_code}: {resp.text[:200]}"


class InstagramService:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings
        self.cipher = TokenCipher(settings)
        self._states: dict[str, float] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # configuration helpers
    # ------------------------------------------------------------------
    @property
    def app_configured(self) -> bool:
        return bool(self.settings.instagram_app_id and self.settings.instagram_app_secret)

    @property
    def redirect_uri(self) -> str:
        return self.settings.public_base_url.rstrip("/") + "/api/auth/instagram/callback"

    @property
    def frontend_url(self) -> str:
        return (self.settings.frontend_url or self.settings.public_base_url).rstrip("/")

    def graph_url(self, path: str) -> str:
        return f"{self.settings.instagram_graph_base.rstrip('/')}/{self.settings.instagram_graph_version}/{path.lstrip('/')}"

    def setup_info(self) -> dict:
        return {
            "app_configured": self.app_configured,
            "redirect_uri": self.redirect_uri,
            "redirect_uri_is_https": self.redirect_uri.startswith("https://"),
            "scopes": SCOPES,
        }

    # ------------------------------------------------------------------
    # OAuth
    # ------------------------------------------------------------------
    def authorization_url(self) -> str:
        if not self.app_configured:
            raise InstagramError("INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET are not set in backend/.env")
        state = secrets.token_urlsafe(24)
        now = time.time()
        with self._lock:
            self._states = {s: exp for s, exp in self._states.items() if exp > now}
            self._states[state] = now + STATE_TTL_SECONDS
        params = {
            "client_id": self.settings.instagram_app_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": ",".join(SCOPES),
            "state": state,
            "enable_fb_login": "0",
            # 0 = reuse the Instagram session already open in this browser, so the
            # user only taps "Allow" instead of logging in again (and facing 2FA)
            "force_authentication": "0",
        }
        return f"{self.settings.instagram_auth_base.rstrip('/')}/oauth/authorize?{urlencode(params)}"

    def consume_state(self, state: str | None) -> bool:
        if not state:
            return False
        with self._lock:
            expires = self._states.pop(state, None)
        return expires is not None and expires > time.time()

    async def complete_login(self, code: str) -> dict:
        """Exchange the authorization code, fetch the profile and store the account."""
        code = code.split("#")[0]  # Instagram appends "#_" to the code
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.settings.instagram_api_base.rstrip('/')}/oauth/access_token",
                data={
                    "client_id": self.settings.instagram_app_id,
                    "client_secret": self.settings.instagram_app_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                    "code": code,
                },
            )
            if resp.status_code >= 400:
                raise InstagramError(f"Could not exchange the login code: {_graph_error(resp)}")
            payload = resp.json()
            data = payload["data"][0] if isinstance(payload.get("data"), list) else payload
            short_token = data["access_token"]
            permissions = data.get("permissions")

            resp = await client.get(
                f"{self.settings.instagram_graph_base.rstrip('/')}/access_token",
                params={"grant_type": "ig_exchange_token", "client_secret": self.settings.instagram_app_secret,
                        "access_token": short_token},
            )
            if resp.status_code >= 400:
                raise InstagramError(f"Could not get a long-lived token: {_graph_error(resp)}")
            long_lived = resp.json()
            token = long_lived["access_token"]
            expires_at = utcnow() + timedelta(seconds=int(long_lived.get("expires_in", 60 * 86400)))

            profile = await self._get(client, self.graph_url("me"), token, {"fields": PROFILE_FIELDS})

        if permissions and isinstance(permissions, str):
            missing = [s for s in SCOPES if s not in permissions]
            if missing:
                logger.warning("Instagram login granted without %s", missing)
        account_type = (profile.get("account_type") or "").upper()
        if account_type and account_type not in ("BUSINESS", "MEDIA_CREATOR", "CREATOR"):
            raise InstagramError("Only Instagram Business or Creator accounts can be connected. "
                                 "Switch the account to a professional account in the Instagram app.")
        ig_user_id = str(profile.get("user_id") or profile.get("id"))
        now = to_iso(utcnow())
        self.db.execute(
            "INSERT INTO instagram_accounts (ig_user_id, username, name, account_type, profile_picture_url, "
            "followers_count, follows_count, media_count, access_token, token_expires_at, token_refreshed_at, "
            "connected_at, last_error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NULL) "
            "ON CONFLICT(ig_user_id) DO UPDATE SET username=excluded.username, name=excluded.name, "
            "account_type=excluded.account_type, profile_picture_url=excluded.profile_picture_url, "
            "followers_count=excluded.followers_count, follows_count=excluded.follows_count, "
            "media_count=excluded.media_count, access_token=excluded.access_token, "
            "token_expires_at=excluded.token_expires_at, token_refreshed_at=excluded.token_refreshed_at, last_error=NULL",
            (ig_user_id, profile.get("username"), profile.get("name"), profile.get("account_type"),
             profile.get("profile_picture_url"), profile.get("followers_count"), profile.get("follows_count"),
             profile.get("media_count"), self.cipher.encrypt(token), to_iso(expires_at), now, now),
        )
        logger.info("Connected Instagram account @%s", profile.get("username"))
        return self.get_account(ig_user_id)

    # ------------------------------------------------------------------
    # accounts
    # ------------------------------------------------------------------
    @staticmethod
    def _public(row: dict) -> dict:
        row = dict(row)
        row.pop("access_token", None)
        return row

    def list_accounts(self) -> list[dict]:
        rows = self.db.query("SELECT * FROM instagram_accounts ORDER BY connected_at")
        for row in rows:
            row.update(self.db.query(
                "SELECT COUNT(*) AS analysed_comments, "
                "SUM(sentiment='positive' AND is_spam=0) AS positive, "
                "SUM(sentiment='neutral' AND is_spam=0) AS neutral, "
                "SUM(sentiment='negative' AND is_spam=0) AS negative, SUM(is_spam) AS spam "
                "FROM mentions WHERE source='instagram' AND origin='live' AND parent_id IN "
                "(SELECT id FROM instagram_media WHERE ig_user_id = ?)", (row["ig_user_id"],))[0])
        return [self._public(r) for r in rows]

    def get_account(self, ig_user_id: str) -> dict | None:
        return next((a for a in self.list_accounts() if a["ig_user_id"] == ig_user_id), None)

    def disconnect(self, ig_user_id: str, delete_data: bool) -> bool:
        if not self.db.scalar("SELECT 1 FROM instagram_accounts WHERE ig_user_id = ?", (ig_user_id,)):
            return False
        if delete_data:
            self.db.execute("DELETE FROM mentions WHERE source='instagram' AND origin='live' AND parent_id IN "
                            "(SELECT id FROM instagram_media WHERE ig_user_id = ?)", (ig_user_id,))
            self.db.execute("DELETE FROM instagram_media WHERE ig_user_id = ?", (ig_user_id,))
        self.db.execute("DELETE FROM instagram_accounts WHERE ig_user_id = ?", (ig_user_id,))
        return True

    def media(self, ig_user_id: str | None, limit: int = 50) -> list[dict]:
        where, params = ("WHERE m.ig_user_id = ?", [ig_user_id]) if ig_user_id else ("", [])
        return self.db.query(
            "SELECT m.*, a.username, "
            "(SELECT COUNT(*) FROM mentions x WHERE x.parent_id = m.id AND x.is_spam = 0) AS analysed, "
            "(SELECT COUNT(*) FROM mentions x WHERE x.parent_id = m.id AND x.is_spam = 0 AND x.sentiment='positive') AS positive, "
            "(SELECT COUNT(*) FROM mentions x WHERE x.parent_id = m.id AND x.is_spam = 0 AND x.sentiment='neutral') AS neutral, "
            "(SELECT COUNT(*) FROM mentions x WHERE x.parent_id = m.id AND x.is_spam = 0 AND x.sentiment='negative') AS negative, "
            "(SELECT COUNT(*) FROM mentions x WHERE x.parent_id = m.id AND x.is_spam = 1) AS spam, "
            "(SELECT AVG(score) FROM mentions x WHERE x.parent_id = m.id AND x.is_spam = 0) AS avg_score "
            f"FROM instagram_media m JOIN instagram_accounts a ON a.ig_user_id = m.ig_user_id {where} "
            "ORDER BY m.timestamp DESC LIMIT ?", params + [limit])

    # ------------------------------------------------------------------
    # Graph API
    # ------------------------------------------------------------------
    async def _get(self, client: httpx.AsyncClient, url, token: str, params: dict | None = None) -> dict:
        # build the full URL ourselves: a paging "next" URL already carries its own
        # query string, and passing params separately would replace it
        target = httpx.URL(url)
        if params:
            target = target.copy_merge_params(params)
        target = target.copy_set_param("access_token", token)
        resp = await client.get(target)
        if resp.status_code >= 400:
            message = _graph_error(resp)
            if resp.status_code in (401, 403) or "(code 190)" in message:
                raise InstagramError(f"Instagram rejected the access token - reconnect the account. {message}")
            if "(code 4)" in message or "(code 32)" in message or resp.status_code == 429:
                raise InstagramError(f"Instagram rate limit reached, will retry later. {message}")
            raise InstagramError(message)
        return resp.json()

    async def _refresh_if_needed(self, client: httpx.AsyncClient, account: dict, token: str) -> str:
        expires = account.get("token_expires_at")
        refreshed = account.get("token_refreshed_at")
        if not expires:
            return token
        days_left = (from_iso(expires) - utcnow()).total_seconds() / 86400
        age_hours = (utcnow() - from_iso(refreshed)).total_seconds() / 3600 if refreshed else 999
        if days_left > REFRESH_WHEN_DAYS_LEFT or age_hours < 24:  # tokens must be 24h old to refresh
            return token
        data = await self._get(client, f"{self.settings.instagram_graph_base.rstrip('/')}/refresh_access_token",
                               token, {"grant_type": "ig_refresh_token"})
        token = data["access_token"]
        expires_at = utcnow() + timedelta(seconds=int(data.get("expires_in", 60 * 86400)))
        self.db.execute("UPDATE instagram_accounts SET access_token=?, token_expires_at=?, token_refreshed_at=? "
                        "WHERE ig_user_id=?", (self.cipher.encrypt(token), to_iso(expires_at), to_iso(utcnow()),
                                               account["ig_user_id"]))
        logger.info("Refreshed Instagram token for @%s", account["username"])
        return token

    async def _paged(self, client, url, token, params, max_pages=MAX_COMMENT_PAGES) -> list[dict]:
        items, page, next_url = [], 0, None
        while page < max_pages:
            data = await self._get(client, next_url or url, token, None if next_url else params)
            items.extend(data.get("data", []))
            next_url = (data.get("paging") or {}).get("next")
            page += 1
            if not next_url:
                break
        return items

    async def sync_account(self, account: dict, force: bool = False) -> list[dict]:
        """Fetch recent posts + new comments. Returns raw mentions for the pipeline."""
        token = self.cipher.decrypt(
            self.db.scalar("SELECT access_token FROM instagram_accounts WHERE ig_user_id=?", (account["ig_user_id"],)))
        raws: list[dict] = []
        async with httpx.AsyncClient(timeout=30) as client:
            token = await self._refresh_if_needed(client, account, token)
            profile = await self._get(client, self.graph_url("me"), token, {"fields": PROFILE_FIELDS})
            username = profile.get("username") or account["username"]
            media_items = await self._paged(client, self.graph_url("me/media"), token,
                                            {"fields": MEDIA_FIELDS, "limit": min(self.settings.instagram_media_limit, 50)},
                                            max_pages=max(1, self.settings.instagram_media_limit // 50 + 1))
            media_items = media_items[: self.settings.instagram_media_limit]
            known = {r["id"]: r for r in self.db.query(
                "SELECT id, comments_count, synced_comments FROM instagram_media WHERE ig_user_id=?",
                (account["ig_user_id"],))}
            now = to_iso(utcnow())
            for m in media_items:
                previous = known.get(m["id"])
                count = int(m.get("comments_count") or 0)
                changed = force or previous is None or previous["synced_comments"] != count
                fetched = 0
                if count and changed:
                    comments = await self._paged(client, self.graph_url(f"{m['id']}/comments"), token,
                                                 {"fields": COMMENT_FIELDS, "limit": 50})
                    fetched = len(comments)
                    if count and not fetched:
                        logger.info("Instagram returned no comments for media %s (it reports %s). Comments on "
                                    "posts published before the account became professional are not available "
                                    "through the API.", m["id"], count)
                    for c in comments:
                        replies = (c.pop("replies", None) or {}).get("data", [])
                        for item in [c, *replies]:
                            # the brand's own replies are not customer opinion
                            if (item.get("username") or "").lower() == username.lower() or not item.get("text"):
                                continue
                            raws.append({
                                "source": "instagram",
                                "origin": "live",
                                "external_id": item["id"],
                                "author": item.get("username"),
                                "text": item["text"],
                                "url": m.get("permalink"),
                                "created_at": to_iso(parse_any_datetime(item.get("timestamp"))),
                                "engagement": int(item.get("like_count") or 0),
                                "parent_id": m["id"],
                            })
                # Track how many comments were actually returned, not how many exist:
                # Instagram serves nothing for media published before the account became
                # professional / was connected, and this way a later sync tries again.
                if count and changed:
                    # store the count we synced at, 0 when nothing came back so we retry later
                    synced = count if fetched else 0
                elif previous is None:
                    synced = 0
                else:
                    synced = previous["synced_comments"]
                self.db.execute(
                    "INSERT INTO instagram_media (id, ig_user_id, caption, media_type, media_url, thumbnail_url, "
                    "permalink, timestamp, like_count, comments_count, synced_comments, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET caption=excluded.caption, "
                    "media_url=excluded.media_url, thumbnail_url=excluded.thumbnail_url, like_count=excluded.like_count, "
                    "comments_count=excluded.comments_count, synced_comments=excluded.synced_comments, "
                    "updated_at=excluded.updated_at",
                    (m["id"], account["ig_user_id"], m.get("caption"), m.get("media_type"), m.get("media_url"),
                     m.get("thumbnail_url"), m.get("permalink"),
                     to_iso(parse_any_datetime(m.get("timestamp"))), m.get("like_count"), count, synced, now),
                )
        self.db.execute(
            "UPDATE instagram_accounts SET username=?, name=?, profile_picture_url=?, followers_count=?, "
            "follows_count=?, media_count=?, last_sync_at=?, last_error=NULL WHERE ig_user_id=?",
            (username, profile.get("name"), profile.get("profile_picture_url"), profile.get("followers_count"),
             profile.get("follows_count"), profile.get("media_count"), to_iso(utcnow()), account["ig_user_id"]))
        return raws

    async def sync_all(self, force: bool = False) -> list[dict]:
        raws = []
        errors = []
        for account in self.db.query("SELECT * FROM instagram_accounts"):
            try:
                raws.extend(await self.sync_account(account, force))
            except (InstagramError, httpx.HTTPError) as exc:
                message = str(exc) or type(exc).__name__
                errors.append(f"@{account['username']}: {message}")
                self.db.execute("UPDATE instagram_accounts SET last_error=?, last_sync_at=? WHERE ig_user_id=?",
                                (message, to_iso(utcnow()), account["ig_user_id"]))
        if errors and not raws:
            raise InstagramError("; ".join(errors))
        return raws


class InstagramCollector:
    """Adapter so connected accounts are polled like every other data source."""

    name = "instagram"
    requires_credentials = True

    def __init__(self, service: InstagramService, settings: Settings):
        self.service = service
        self.interval = settings.instagram_poll_seconds
        self.last_poll: float | None = None
        self.last_count = 0
        self.last_error: str | None = None
        self.total = 0

    def configured(self) -> bool:
        return bool(self.service.db.scalar("SELECT 1 FROM instagram_accounts LIMIT 1"))

    def status(self) -> dict:
        return {
            "name": self.name,
            "configured": self.configured(),
            "requires_credentials": self.requires_credentials,
            "app_configured": self.service.app_configured,
            "last_poll": self.last_poll,
            "last_count": self.last_count,
            "last_error": self.last_error,
            "total_collected": self.total,
        }

    async def poll(self, brand: str, keywords: list[str]) -> list[dict]:
        if not self.configured():
            return []
        return await self.service.sync_all()
