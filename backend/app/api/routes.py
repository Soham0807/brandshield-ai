"""REST + WebSocket API consumed by the React dashboard."""

import asyncio
import csv
import io
import json
from typing import Literal

import httpx

from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field

from app.db import decode_mention, to_iso, utcnow
from app.config import write_env
from app.integrations.instagram import InstagramError
from app.integrations.instagram_public import InstagramPublicError, normalise_username
from app.integrations.youtube import YouTubeError
from app.integrations.tunnel import TunnelError
from app.nlp.preprocess import preprocess

router = APIRouter(prefix="/api")
_background_tasks: set[asyncio.Task] = set()  # keeps fire-and-forget tasks alive
ws_router = APIRouter()


def core(request: Request):
    return request.app.state.core


def _require_model(app):
    if not app.model.ready.is_set():
        raise HTTPException(503, "The sentiment model is still loading, try again in a few seconds")


# ---------------------------------------------------------------------------
# Dashboard data
# ---------------------------------------------------------------------------
@router.get("/health")
def health(request: Request):
    app = core(request)
    return {"status": "ok", "model_ready": app.model.ready.is_set(), "time": to_iso(utcnow())}


@router.get("/status")
def status(request: Request):
    return core(request).public_status()


@router.get("/overview")
async def overview(request: Request, hours: float = Query(24, gt=0, le=24 * 90)):
    return await asyncio.to_thread(core(request).analytics.overview, hours)


@router.get("/trends")
async def trends(request: Request, hours: float = Query(24, gt=0, le=24 * 90),
                 bucket_minutes: int | None = Query(None, ge=5, le=1440)):
    return await asyncio.to_thread(core(request).analytics.trends, hours, bucket_minutes)


@router.get("/aspects")
async def aspects(request: Request, hours: float = Query(24, gt=0, le=24 * 90)):
    return await asyncio.to_thread(core(request).analytics.aspects, hours)


@router.get("/anomalies")
async def anomalies(request: Request, hours: float = Query(48, gt=0, le=72)):
    return await asyncio.to_thread(core(request).analytics.anomalies, hours)


@router.get("/forecast")
async def forecast(request: Request):
    app = core(request)
    if not app.analytics.forecast_data.get("computed_at"):
        await asyncio.to_thread(app.analytics.refresh_forecast)
    return app.analytics.public_forecast()


@router.get("/risk")
def risk(request: Request):
    latest = core(request).analytics.latest
    return {"computed_at": latest.get("computed_at"), **latest.get("risk", {}),
            "incidents": latest.get("incidents", [])}


# ---------------------------------------------------------------------------
# Mentions
# ---------------------------------------------------------------------------
@router.get("/mentions")
def mentions(request: Request,
             sentiment: Literal["positive", "neutral", "negative"] | None = None,
             source: str | None = None,
             aspect: str | None = None,
             language: str | None = None,
             spam: bool | None = None,
             origin: Literal["live", "simulated"] | None = None,
             parent_id: str | None = Query(None, max_length=64),
             q: str | None = Query(None, max_length=200),
             hours: float | None = Query(None, gt=0, le=24 * 90),
             sort: Literal["newest", "oldest", "engagement", "most_negative"] = "newest",
             limit: int = Query(50, ge=1, le=500),
             offset: int = Query(0, ge=0)):
    where, params = [], []
    if sentiment:
        where.append("sentiment = ?")
        params.append(sentiment)
    if source:
        where.append("source = ?")
        params.append(source)
    if language:
        where.append("language = ?")
        params.append(language)
    if spam is not None:
        where.append("is_spam = ?")
        params.append(int(spam))
    if origin:
        where.append("origin = ?")
        params.append(origin)
    if parent_id:
        where.append("parent_id = ?")
        params.append(parent_id)
    if aspect:
        where.append("aspects LIKE ?")
        params.append(f'%"aspect": "{aspect}"%')
    if q:
        where.append("(text LIKE ? OR author LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if hours:
        from datetime import timedelta
        where.append("created_at >= ?")
        params.append(to_iso(utcnow() - timedelta(hours=hours)))
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    order = {"newest": "created_at DESC", "oldest": "created_at ASC",
             "engagement": "engagement DESC", "most_negative": "score ASC"}[sort]
    db = core(request).db
    total = db.scalar(f"SELECT COUNT(*) FROM mentions {clause}", params)
    rows = db.query(f"SELECT * FROM mentions {clause} ORDER BY {order} LIMIT ? OFFSET ?", params + [limit, offset])
    return {"total": total, "items": [decode_mention(r) for r in rows]}


@router.get("/mentions/facets")
def mention_facets(request: Request):
    db = core(request).db
    return {
        "sources": [r["source"] for r in db.query("SELECT DISTINCT source FROM mentions ORDER BY source")],
        "languages": [r["language"] for r in db.query(
            "SELECT language, COUNT(*) n FROM mentions GROUP BY language ORDER BY n DESC LIMIT 20")],
        "aspects": list(core(request).runtime.get()["aspects"].keys()),
    }


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    store: bool = False
    source: str = "manual"
    author: str | None = None


@router.post("/analyze")
async def analyze(request: Request, body: AnalyzeRequest):
    app = core(request)
    _require_model(app)
    prepared = preprocess(body.text)
    started = asyncio.get_running_loop().time()
    sentiment = (await asyncio.to_thread(app.model.predict, [prepared.model_text]))[0]
    aspect_items = (await asyncio.to_thread(app.aspects.analyze_batch, [prepared.model_text], [sentiment],
                                            app.model))[0]
    elapsed_ms = (asyncio.get_running_loop().time() - started) * 1000
    stored = None
    if body.store:
        raw = {"source": body.source, "author": body.author, "text": body.text}
        result = await app.processor.process_batch([raw])
        stored = result[0]["id"] if result else "duplicate"
    return {
        "preprocessing": prepared.to_dict(),
        "sentiment": sentiment,
        "aspects": aspect_items,
        "clauses": app.aspects.extract_clauses(prepared.model_text),
        "model": app.model.active_model,
        "processing_ms": round(elapsed_ms, 1),
        "stored_id": stored,
    }


class IngestItem(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    source: str = "api"
    author: str | None = None
    url: str | None = None
    created_at: str | None = None
    external_id: str | None = None
    engagement: int = 0


class IngestRequest(BaseModel):
    items: list[IngestItem] = Field(..., min_length=1, max_length=5000)


@router.post("/ingest")
async def ingest(request: Request, body: IngestRequest):
    """Push mentions from any external system into the streaming pipeline."""
    app = core(request)
    for item in body.items:
        await app.publish(item.model_dump())
    return {"queued": len(body.items), "bus": app.bus.name}


@router.post("/ingest/csv")
async def ingest_csv(request: Request, file: UploadFile = File(...)):
    """Upload a CSV with a `text` (or `comment`) column and optional
    `timestamp`/`created_at`, `author`, `source`, `engagement` columns."""
    app = core(request)
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, "CSV must be smaller than 20 MB")
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    except UnicodeDecodeError:
        raise HTTPException(400, "CSV must be UTF-8 encoded")
    fields = {f.lower().strip(): f for f in (reader.fieldnames or [])}
    text_col = fields.get("text") or fields.get("comment") or fields.get("content") or fields.get("message")
    if not text_col:
        raise HTTPException(400, "CSV needs a 'text' or 'comment' column")
    time_col = fields.get("created_at") or fields.get("timestamp") or fields.get("date")
    queued = 0
    for row in reader:
        text = (row.get(text_col) or "").strip()
        if not text:
            continue
        engagement = row.get(fields.get("engagement", ""), 0) or 0
        await app.publish({
            "text": text,
            "source": (row.get(fields.get("source", "")) or "csv").strip().lower(),
            "author": row.get(fields.get("author", "")) or None,
            "created_at": row.get(time_col) if time_col else None,
            "engagement": int(float(engagement)) if str(engagement).replace(".", "", 1).isdigit() else 0,
        })
        queued += 1
        if queued >= 50_000:
            break
    return {"queued": queued, "filename": file.filename}


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
@router.get("/alerts")
def list_alerts(request: Request, status: Literal["open", "acknowledged", "dismissed"] | None = None,
                limit: int = Query(100, ge=1, le=500)):
    engine = core(request).alerts
    items = engine.list(status, limit)
    counts = {r["severity"]: r["n"] for r in core(request).db.query(
        "SELECT severity, COUNT(*) n FROM alerts WHERE status='open' GROUP BY severity")}
    return {"items": items, "open_counts": counts}


@router.post("/alerts/{alert_id}/{action}")
async def update_alert(request: Request, alert_id: int, action: Literal["acknowledge", "dismiss", "reopen"]):
    status_value = {"acknowledge": "acknowledged", "dismiss": "dismissed", "reopen": "open"}[action]
    if not core(request).alerts.set_status(alert_id, status_value):
        raise HTTPException(404, "Alert not found")
    await core(request).hub.broadcast("alert_updated", {"id": alert_id, "status": status_value})
    return {"id": alert_id, "status": status_value}


@router.post("/alerts/test")
async def test_alert(request: Request):
    app = core(request)
    cfg = app.runtime.get()
    alert = {"id": 0, "severity": "medium", "type": "test", "title": "Test notification",
             "message": "This is a test alert from BrandShield AI. Notifications are working.",
             "created_at": to_iso(utcnow()), "meta": {}, "status": "open"}
    delivery = await app.notifier.send(alert, cfg["notifications"], cfg["brand_name"], force=True)
    await app.hub.broadcast("alert", alert)
    return {"delivery": delivery, "channels": app.notifier.channels_status()}


# ---------------------------------------------------------------------------
# Settings / simulator / system
# ---------------------------------------------------------------------------
@router.get("/settings")
def get_settings(request: Request):
    app = core(request)
    return {"config": app.runtime.get(), "channels": app.notifier.channels_status(),
            "collectors": {n: c.status() for n, c in app.collectors.items()}}


@router.put("/settings")
async def put_settings(request: Request):
    app = core(request)
    try:
        patch = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(400, "Body must be JSON")
    if not isinstance(patch, dict):
        raise HTTPException(400, "Body must be a JSON object")
    try:
        cfg = app.runtime.update(patch)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc))
    if "sources" in patch or "keywords" in patch or "brand_name" in patch:
        app.wake_collectors()
    if "aspects" in patch and app.model.ready.is_set():
        task = asyncio.create_task(app.retag_topics())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    await app.hub.broadcast("status", app.public_status())
    return {"config": cfg}


@router.get("/settings/topic-presets")
def topic_presets():
    from app.nlp.aspects import ASPECT_PRESETS
    return {"presets": [{"id": k, "label": v["label"], "aspects": v["aspects"]} for k, v in ASPECT_PRESETS.items()]}


@router.post("/settings/reset")
def reset_settings(request: Request):
    return {"config": core(request).runtime.reset()}


class CrisisRequest(BaseModel):
    aspect: str = "delivery"
    minutes: int = Field(20, ge=1, le=240)
    intensity: float = Field(0.8, ge=0.1, le=1.0)


@router.post("/simulator/crisis")
async def start_crisis(request: Request, body: CrisisRequest):
    from app.collectors.simulator import TEMPLATES
    if body.aspect not in TEMPLATES:
        raise HTTPException(422, f"aspect must be one of {sorted(TEMPLATES)}")
    app = core(request)
    if not app.runtime.get()["sources"]["simulator"]:
        raise HTTPException(409, "Enable the simulator source first")
    state = app.crisis(body.aspect, body.minutes, body.intensity)
    await app.hub.broadcast("status", app.public_status())
    return state


@router.post("/simulator/crisis/stop")
async def stop_crisis(request: Request):
    app = core(request)
    app.simulator.stop_crisis()
    await app.hub.broadcast("status", app.public_status())
    return app.simulator.crisis.to_dict(utcnow())


@router.post("/collectors/poll")
def poll_now(request: Request):
    core(request).wake_collectors()
    return {"ok": True}


class ResetRequest(BaseModel):
    confirm: bool = False
    reseed: bool = True


@router.post("/data/reset")
async def reset_data(request: Request, body: ResetRequest):
    if not body.confirm:
        raise HTTPException(400, "Set confirm=true to delete all mentions and alerts")
    app = core(request)
    _require_model(app)
    return await app.reset_data(body.reseed)


@router.get("/system/metrics")
def system_metrics(request: Request):
    app = core(request)
    return app.metrics.snapshot(app.bus.depth() if app.bus else None, app.model) | {"bus": app.bus.name}


@router.get("/system/evaluation")
def evaluation(request: Request):
    path = core(request).settings.evaluation_path
    if not path.exists():
        return {"available": False}
    return {"available": True, **json.loads(path.read_text(encoding="utf-8"))}


_evaluation_task: dict = {"running": False, "error": None}


@router.post("/system/evaluation/run")
async def run_evaluation(request: Request):
    app = core(request)
    _require_model(app)
    if _evaluation_task["running"]:
        raise HTTPException(409, "An evaluation is already running")

    async def job():
        from scripts.evaluate_model import evaluate_datasets
        _evaluation_task.update(running=True, error=None)
        try:
            await asyncio.to_thread(evaluate_datasets, app.model, ["domain", "real"], app.settings.evaluation_path, app.aspects)
        except Exception as exc:
            _evaluation_task["error"] = str(exc)
        finally:
            _evaluation_task["running"] = False
            await app.hub.broadcast("evaluation", {"done": True, "error": _evaluation_task["error"]})

    asyncio.create_task(job())
    return {"started": True}


@router.get("/system/evaluation/status")
def evaluation_status():
    return _evaluation_task


# ---------------------------------------------------------------------------
# Instagram (OAuth login with the official Instagram API)
# ---------------------------------------------------------------------------
def _frontend_redirect(app, path: str, **params) -> RedirectResponse:
    query = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"{app.instagram.frontend_url}{path}{query}", status_code=303)


def _setup_only(request: Request) -> None:
    """Setup endpoints are restricted to the machine running BrandShield.

    While the tunnel is open the dashboard is reachable from the internet;
    cloudflared adds X-Forwarded-For, so those visitors are treated as remote.
    """
    host = (request.client.host if request.client else "") or ""
    forwarded = request.headers.get("x-forwarded-for") or request.headers.get("cf-connecting-ip")
    if forwarded or host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(403, "This action is only allowed from the computer running BrandShield AI")


class CredentialsRequest(BaseModel):
    app_id: str = Field(..., min_length=3, max_length=64, pattern=r"^[0-9A-Za-z._-]+$")
    app_secret: str = Field(..., min_length=8, max_length=128, pattern=r"^[0-9A-Za-z._-]+$")


@router.post("/instagram/credentials")
async def save_instagram_credentials(request: Request, body: CredentialsRequest):
    """Store the Meta app keys in backend/.env and apply them without a restart."""
    app = core(request)
    _setup_only(request)
    app.settings.instagram_app_id = body.app_id.strip()
    app.settings.instagram_app_secret = body.app_secret.strip()
    path = write_env({"INSTAGRAM_APP_ID": app.settings.instagram_app_id,
                      "INSTAGRAM_APP_SECRET": app.settings.instagram_app_secret})
    await app.hub.broadcast("status", app.public_status())
    return {"app_configured": app.instagram.app_configured, "saved_to": str(path),
            "setup": app.instagram.setup_info()}


class ApiKeysRequest(BaseModel):
    """Keys for the public sources, stored in backend/.env."""
    youtube_api_key: str | None = Field(None, max_length=200)
    reddit_client_id: str | None = Field(None, max_length=200)
    reddit_client_secret: str | None = Field(None, max_length=200)
    twitter_bearer_token: str | None = Field(None, max_length=500)
    apify_token: str | None = Field(None, max_length=200)
    appstore_app_id: str | None = Field(None, max_length=40, pattern=r"^[0-9]*$")
    appstore_country: str | None = Field(None, max_length=2, pattern=r"^[A-Za-z]*$")


@router.get("/keys")
def api_keys(request: Request):
    """Which keys are present (never returns the values themselves)."""
    s = core(request).settings
    return {"configured": {name: bool(getattr(s, name)) for name in
                           ("youtube_api_key", "reddit_client_id", "reddit_client_secret",
                            "twitter_bearer_token", "apify_token", "instagram_app_id", "instagram_app_secret")},
            "appstore_app_id": s.appstore_app_id, "appstore_country": s.appstore_country}


@router.put("/keys")
async def save_api_keys(request: Request, body: ApiKeysRequest):
    app = core(request)
    _setup_only(request)
    updates = {k: v.strip() for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No keys given")
    for key, value in updates.items():
        setattr(app.settings, key, value)
    write_env({k.upper(): v for k, v in updates.items()})
    app.wake_collectors()
    await app.hub.broadcast("status", app.public_status())
    return {"saved": sorted(updates), "collectors": {n: c.status() for n, c in app.collectors.items()}}


@router.post("/instagram/tunnel/{action}")
async def instagram_tunnel(request: Request, action: Literal["start", "stop"]):
    """Start or stop the public https tunnel used for the OAuth redirect."""
    app = core(request)
    _setup_only(request)
    try:
        status = await (app.tunnel.start() if action == "start" else app.tunnel.stop())
    except TunnelError as exc:
        raise HTTPException(502, str(exc))
    await app.hub.broadcast("status", app.public_status())
    return {**status, "setup": app.instagram.setup_info()}


@router.get("/instagram/status")
def instagram_status(request: Request):
    app = core(request)
    return {
        **app.instagram.setup_info(),
        "tunnel": app.tunnel.status(),
        "accounts": app.instagram.list_accounts(),
        "source_enabled": bool(app.runtime.get()["sources"].get("instagram")),
        "collector": app.collectors["instagram"].status(),
        "simulator_enabled": bool(app.runtime.get()["sources"].get("simulator")),
        "simulated_mentions": app.db.scalar("SELECT COUNT(*) FROM mentions WHERE origin = 'simulated'"),
    }


@router.get("/auth/instagram/login", include_in_schema=False)
def instagram_login(request: Request):
    """Redirect the browser to Instagram's own login + consent page."""
    app = core(request)
    try:
        return RedirectResponse(app.instagram.authorization_url(), status_code=303)
    except InstagramError as exc:
        return _frontend_redirect(app, "/instagram", error=str(exc))


@router.get("/auth/instagram/callback", include_in_schema=False)
async def instagram_callback(request: Request, code: str | None = None, state: str | None = None,
                             error: str | None = None, error_reason: str | None = None,
                             error_description: str | None = None):
    app = core(request)
    if error:
        message = "Instagram login was cancelled." if error_reason == "user_denied" else             f"Instagram login failed: {error_description or error}"
        return _frontend_redirect(app, "/instagram", error=message)
    if not app.instagram.consume_state(state):
        return _frontend_redirect(app, "/instagram", error="Login session expired or is invalid. Please try again.")
    if not code:
        return _frontend_redirect(app, "/instagram", error="Instagram did not return an authorization code.")
    try:
        account = await app.instagram.complete_login(code)
    except (InstagramError, KeyError, ValueError) as exc:
        return _frontend_redirect(app, "/instagram", error=str(exc) or "Could not complete the Instagram login.")
    except Exception as exc:  # network problems etc.
        return _frontend_redirect(app, "/instagram", error=f"Could not reach Instagram: {type(exc).__name__}")
    if not app.runtime.get()["sources"].get("instagram"):
        app.runtime.update({"sources": {"instagram": True}})
    app.wake_collectors()
    await app.hub.broadcast("status", app.public_status())
    return _frontend_redirect(app, "/instagram", connected=account["username"])


@router.get("/instagram/media")
def instagram_media(request: Request, ig_user_id: str | None = None, limit: int = Query(50, ge=1, le=200)):
    return {"items": core(request).instagram.media(ig_user_id, limit)}


class SyncRequest(BaseModel):
    force: bool = False


@router.post("/instagram/accounts/{ig_user_id}/sync")
async def instagram_sync(request: Request, ig_user_id: str, body: SyncRequest):
    app = core(request)
    _require_model(app)
    try:
        queued = await app.sync_instagram(ig_user_id, body.force)
    except InstagramError as exc:
        raise HTTPException(502 if "Account not found" not in str(exc) else 404, str(exc))
    return {"queued_comments": queued, "account": app.instagram.get_account(ig_user_id)}


@router.delete("/instagram/accounts/{ig_user_id}")
async def instagram_disconnect(request: Request, ig_user_id: str, delete_data: bool = False):
    app = core(request)
    if not app.instagram.disconnect(ig_user_id, delete_data):
        raise HTTPException(404, "Account not found")
    app.analytics._cache.clear()
    await app.hub.broadcast("status", app.public_status())
    return {"disconnected": ig_user_id, "deleted_data": delete_data}


class LiveOnlyRequest(BaseModel):
    confirm: bool = False
    rename_brand: bool = True


@router.post("/data/use-live-only")
async def use_live_only(request: Request, body: LiveOnlyRequest):
    if not body.confirm:
        raise HTTPException(400, "Set confirm=true to turn off the simulator and delete simulated data")
    return await core(request).use_live_data_only(body.rename_brand)


# ---------------------------------------------------------------------------
# Public Instagram pages of any brand (no Instagram login, via Apify)
# ---------------------------------------------------------------------------
class InstagramPageRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200, description="@handle or profile URL")
    set_brand: bool = True


@router.get("/instagram/pages")
def instagram_pages(request: Request):
    app = core(request)
    return {
        "configured": app.instagram_pages.configured,
        "pages": app.instagram_pages.list_pages(),
        "collector": app.collectors["instagram_pages"].status(),
        "source_enabled": bool(app.runtime.get()["sources"].get("instagram_pages")),
    }


# Instagram's CDN refuses to show its images on other sites, so they are relayed.
# Only Instagram/Facebook CDN hosts are allowed, so this cannot fetch arbitrary URLs.
_IMAGE_HOSTS = (".cdninstagram.com", ".fbcdn.net")


@router.get("/instagram/image", include_in_schema=False)
async def instagram_image(url: str = Query(..., max_length=3000)):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(_IMAGE_HOSTS):
        raise HTTPException(400, "Only Instagram image URLs are allowed")
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
    except httpx.HTTPError:
        raise HTTPException(502, "Could not load the image")
    content_type = resp.headers.get("content-type", "")
    if resp.status_code != 200 or not content_type.startswith("image/"):
        raise HTTPException(404, "Image not available")
    return Response(resp.content, media_type=content_type, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/instagram/pages/posts")
def instagram_page_posts(request: Request, username: str | None = Query(None, max_length=30),
                         limit: int = Query(60, ge=1, le=200)):
    return {"items": core(request).instagram_pages.posts(username.lower() if username else None, limit)}


async def _sync_page_in_background(app, username: str, force: bool) -> None:
    try:
        await app.sync_instagram_page(username, force)
    except Exception as exc:  # shown on the page card via last_error
        app.instagram_pages.set_error(username, str(exc) or type(exc).__name__)
    await app.hub.broadcast("status", app.public_status())
    await app.hub.broadcast("instagram_pages", {"username": username})


@router.post("/instagram/pages")
async def add_instagram_page(request: Request, body: InstagramPageRequest):
    """Look up a public page, save it, and import its comments in the background."""
    app = core(request)
    _require_model(app)
    if not app.instagram_pages.configured:
        raise HTTPException(503, "Monitoring public Instagram pages isn't switched on for this installation yet.")
    try:
        username = normalise_username(body.query)
    except InstagramPublicError as exc:
        raise HTTPException(422, str(exc))
    try:
        async with httpx.AsyncClient(timeout=app.settings.apify_timeout_seconds) as client:
            profile = await app.instagram_pages.fetch_profile(client, username)
    except InstagramPublicError as exc:
        raise HTTPException(422 if "No public" in str(exc) or "private" in str(exc) else 502, str(exc))
    page = app.instagram_pages.save_page(profile)
    patch = {"sources": {"instagram_pages": True}}
    if body.set_brand:
        patch["brand_name"] = profile.get("fullName") or username
        patch["keywords"] = sorted({username, f"@{username}", profile.get("fullName") or username})
    app.runtime.update(patch)
    task = asyncio.create_task(_sync_page_in_background(app, username, True))
    _background_tasks.add(task)  # keep a reference so the task is not garbage-collected
    task.add_done_callback(_background_tasks.discard)
    await app.hub.broadcast("status", app.public_status())
    return {"page": page, "importing": True}


@router.post("/instagram/pages/{username}/sync")
async def sync_instagram_page(request: Request, username: str, body: SyncRequest):
    app = core(request)
    _require_model(app)
    username = username.lower()
    if not app.instagram_pages.get_page(username):
        raise HTTPException(404, "Page not found")
    try:
        queued = await app.sync_instagram_page(username, body.force)
    except InstagramPublicError as exc:
        raise HTTPException(502, str(exc))
    return {"queued_comments": queued, "page": app.instagram_pages.get_page(username)}


@router.delete("/instagram/pages/{username}")
async def remove_instagram_page(request: Request, username: str, delete_data: bool = False):
    app = core(request)
    if not app.instagram_pages.remove_page(username.lower(), delete_data):
        raise HTTPException(404, "Page not found")
    app.analytics._cache.clear()
    await app.hub.broadcast("status", app.public_status())
    return {"removed": username.lower(), "deleted_data": delete_data}


# ---------------------------------------------------------------------------
# YouTube channels (public data, read-only)
# ---------------------------------------------------------------------------
@router.get("/youtube/status")
def youtube_status(request: Request):
    app = core(request)
    return {
        "configured": app.youtube.configured,
        "channels": app.youtube.list_channels(),
        "collector": app.collectors["youtube"].status(),
        "source_enabled": bool(app.runtime.get()["sources"].get("youtube")),
        "simulated_mentions": app.db.scalar("SELECT COUNT(*) FROM mentions WHERE origin = 'simulated'"),
    }


class ChannelRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=120,
                       description="@handle, channel URL, channel id or channel name")
    set_brand: bool = True


@router.post("/youtube/channels")
async def add_youtube_channel(request: Request, body: ChannelRequest):
    """Resolve a channel and start monitoring its videos + comments."""
    app = core(request)
    _require_model(app)
    try:
        found = await app.youtube.resolve(body.query)
    except YouTubeError as exc:
        raise HTTPException(422, str(exc))
    channel = app.youtube.save_channel(found)
    patch = {"sources": {"youtube": True}}
    if body.set_brand:
        patch["brand_name"] = channel["title"]
        patch["keywords"] = [c for c in {channel["title"], f"@{channel['handle']}" if channel["handle"] else None} if c]
    app.runtime.update(patch)
    try:
        queued = await app.sync_youtube(channel["channel_id"], force=True)
    except YouTubeError as exc:
        raise HTTPException(502, str(exc))
    await app.hub.broadcast("status", app.public_status())
    return {"channel": app.youtube.get_channel(channel["channel_id"]), "queued_comments": queued}


@router.get("/youtube/videos")
def youtube_videos(request: Request, channel_id: str | None = None, limit: int = Query(60, ge=1, le=200)):
    return {"items": core(request).youtube.videos(channel_id, limit)}


@router.post("/youtube/channels/{channel_id}/sync")
async def sync_youtube_channel(request: Request, channel_id: str, body: SyncRequest):
    app = core(request)
    _require_model(app)
    try:
        queued = await app.sync_youtube(channel_id, body.force)
    except YouTubeError as exc:
        raise HTTPException(404 if "not found" in str(exc).lower() else 502, str(exc))
    return {"queued_comments": queued, "channel": app.youtube.get_channel(channel_id)}


@router.delete("/youtube/channels/{channel_id}")
async def remove_youtube_channel(request: Request, channel_id: str, delete_data: bool = False):
    app = core(request)
    if not app.youtube.remove_channel(channel_id, delete_data):
        raise HTTPException(404, "Channel not found")
    app.analytics._cache.clear()
    await app.hub.broadcast("status", app.public_status())
    return {"removed": channel_id, "deleted_data": delete_data}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
@ws_router.websocket("/ws")
async def websocket(ws: WebSocket):
    app = ws.app.state.core
    await app.hub.connect(ws)
    try:
        await ws.send_text(json.dumps({"type": "status", "data": app.public_status()}))
        while True:
            message = await ws.receive_text()
            if message == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        await app.hub.disconnect(ws)
