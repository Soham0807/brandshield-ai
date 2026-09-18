"""Application container: wires every component together and runs the
background tasks (collectors, stream processor, analytics, forecasting)."""

import asyncio
import logging
import random
import time
from datetime import timedelta

from app.alerts.engine import AlertEngine
from app.alerts.notifiers import Notifier
from app.analytics.service import AnalyticsService
from app.collectors.platforms import CollectorError, RedditCollector, RssCollector, TwitterCollector
from app.collectors.public_sources import AppStoreCollector
from app.collectors.simulator import MentionSimulator
from app.config import Settings
from app.db import Database, to_iso, utcnow
from app.integrations.instagram import InstagramCollector, InstagramError, InstagramService
from app.integrations.tunnel import TunnelManager
from app.integrations.youtube import YouTubeChannelCollector, YouTubeError, YouTubeService
from app.nlp.aspects import AspectExtractor
from app.nlp.sentiment import SentimentModel
from app.pipeline.bus import create_bus
from app.pipeline.hub import Hub
from app.pipeline.metrics import PipelineMetrics
from app.pipeline.processor import Processor
from app.runtime import RuntimeConfig

logger = logging.getLogger("brandshield.core")


class App:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = Database(settings.database_path)
        self.runtime = RuntimeConfig(self.db, settings)
        self.hub = Hub()
        self.metrics = PipelineMetrics()
        self.model = SentimentModel(settings.sentiment_model, settings.fallback_sentiment_model,
                                    settings.model_batch_size, settings.model_max_length)
        self.aspects = AspectExtractor(self.runtime.get()["aspects"])
        self.runtime.subscribe(lambda cfg: self.aspects.update(cfg["aspects"]))
        self.analytics = AnalyticsService(self.db, self.runtime, settings)
        self.notifier = Notifier(settings)
        self.alerts = AlertEngine(self.db, self.runtime, self.notifier, self.hub)
        self.processor = Processor(self.db, self.model, self.aspects, self.metrics, self._on_processed)
        self.simulator = MentionSimulator()
        self.instagram = InstagramService(self.db, settings)
        self.youtube = YouTubeService(self.db, settings)
        self.tunnel = TunnelManager(settings, db=self.db, on_change=self._tunnel_changed)
        self.collectors = {
            "reddit": RedditCollector(settings),
            "rss": RssCollector(settings),
            "twitter": TwitterCollector(settings),
            "youtube": YouTubeChannelCollector(self.youtube, settings),
            "appstore": AppStoreCollector(settings),
            "instagram": InstagramCollector(self.instagram, settings),
        }
        self.bus = None
        self.status = {"model": "loading", "seeding": None}
        self._tasks: list[asyncio.Task] = []
        self._wake_collectors = asyncio.Event()

    def _tunnel_changed(self, status: dict) -> None:
        try:
            asyncio.get_running_loop().create_task(self.hub.broadcast("tunnel", status))
        except RuntimeError:
            pass

    # ------------------------------------------------------------------
    async def start(self) -> None:
        self.bus = await create_bus(self.settings)
        await self.tunnel.restore()   # keep a public address that is still running
        self._spawn(self._load_model(), "model-loader")
        self._spawn(self.processor.run(self.bus), "processor")
        self._spawn(self._seed_then_simulate(), "simulator")
        for name in self.collectors:
            self._spawn(self._collector_loop(name), f"collector-{name}")
        self._spawn(self._analytics_loop(), "analytics")
        self._spawn(self._forecast_loop(), "forecast")
        self._spawn(self._metrics_loop(), "metrics")

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        # the tunnel keeps running on purpose: its address stays registered with Meta
        if self.bus:
            await self.bus.stop()
        self.db.close()

    def _spawn(self, coro, name: str) -> None:
        task = asyncio.create_task(coro, name=name)

        def done(t: asyncio.Task):
            if not t.cancelled() and t.exception():
                logger.error("Background task %s crashed", name, exc_info=t.exception())

        task.add_done_callback(done)
        self._tasks.append(task)

    # ------------------------------------------------------------------
    async def publish(self, raw: dict) -> None:
        raw = dict(raw)
        raw["ingested_at"] = to_iso(utcnow())
        raw["_ingested_monotonic"] = time.monotonic()
        if hasattr(raw.get("created_at"), "strftime"):
            raw["created_at"] = to_iso(raw["created_at"])
        await self.bus.publish(raw)
        self.metrics.record_ingested()

    async def _on_processed(self, mentions: list[dict]) -> None:
        await self.hub.broadcast("mentions", mentions[:50])
        await self.alerts.check_mentions(mentions)

    async def _load_model(self) -> None:
        try:
            await asyncio.to_thread(self.model.load)
            self.status["model"] = "ready"
            await self.hub.broadcast("status", self.public_status())
        except Exception as exc:
            self.status["model"] = f"error: {exc}"
            logger.exception("Model loading failed")

    # ------------------------------------------------------------------
    async def seed_history(self, days: int) -> int:
        cfg = self.runtime.get()
        now = utcnow()
        mentions = self.simulator.history(cfg["brand_name"], days, cfg["simulator_rate_per_min"], now)
        total = len(mentions)
        self.status["seeding"] = {"total": total, "done": 0}
        await self.hub.broadcast("status", self.public_status())
        for i in range(0, total, 256):
            chunk = mentions[i:i + 256]
            for m in chunk:
                m["created_at"] = to_iso(m["created_at"])
            await self.processor.process_batch(chunk, broadcast=False)
            self.status["seeding"]["done"] = min(total, i + 256)
            if (i // 256) % 8 == 0:
                await self.hub.broadcast("status", self.public_status())
        self.status["seeding"] = None
        self.analytics._cache.clear()
        await asyncio.to_thread(self.analytics.refresh_forecast)
        await asyncio.to_thread(self.analytics.compute_snapshot)
        await self.hub.broadcast("status", self.public_status())
        await self.hub.broadcast("refresh", {"reason": "seeded"})
        return total

    async def _seed_then_simulate(self) -> None:
        await asyncio.to_thread(self.model.ready.wait)
        cfg = self.runtime.get()
        if cfg["sources"]["simulator"] and self.settings.seed_history_days > 0 and self.db.count_mentions() == 0:
            logger.info("Empty database - generating %s days of simulated history", self.settings.seed_history_days)
            try:
                count = await self.seed_history(self.settings.seed_history_days)
                logger.info("Seeded %s historical mentions", count)
            except Exception:
                self.status["seeding"] = None
                logger.exception("Seeding failed")
        while True:
            cfg = self.runtime.get()
            if not cfg["sources"]["simulator"]:
                await asyncio.sleep(2)
                continue
            now = utcnow()
            per_min = cfg["simulator_rate_per_min"] / 1.1 * self.simulator.rate_multiplier(now)
            await asyncio.sleep(min(self.simulator.rng.expovariate(per_min / 60), 30))
            cfg = self.runtime.get()
            if not cfg["sources"]["simulator"]:  # switched off while we were sleeping
                continue
            mention = self.simulator.generate(cfg["brand_name"], utcnow())
            await self.publish(mention)

    async def _collector_loop(self, name: str) -> None:
        collector = self.collectors[name]
        await asyncio.to_thread(self.model.ready.wait)
        while True:
            cfg = self.runtime.get()
            if cfg["sources"].get(name):
                try:
                    items = await collector.poll(cfg["brand_name"], cfg["keywords"])
                    collector.last_error = None
                    new = 0
                    for item in items:
                        if item.get("text"):
                            await self.publish(item)
                            new += 1
                    collector.last_count = new
                    collector.total += new
                except (CollectorError, InstagramError, YouTubeError) as exc:
                    collector.last_error = str(exc)
                except Exception as exc:
                    collector.last_error = f"{type(exc).__name__}: {exc}"
                    logger.warning("Collector %s failed: %s", name, exc)
                collector.last_poll = time.time()
            try:
                interval = getattr(collector, "interval", self.settings.poll_interval_seconds)
                await asyncio.wait_for(self._wake_collectors.wait(), timeout=interval + random.uniform(0, 10))
                self._wake_collectors.clear()
            except TimeoutError:
                pass

    def wake_collectors(self) -> None:
        self._wake_collectors.set()

    async def _analytics_loop(self) -> None:
        await asyncio.to_thread(self.model.ready.wait)
        await asyncio.sleep(3)
        while True:
            try:
                if self.status["seeding"] is None:
                    snapshot = await asyncio.to_thread(self.analytics.compute_snapshot)
                    await self.alerts.evaluate(snapshot, self.analytics.forecast_data)
                    await self.hub.broadcast("risk", snapshot["risk"])
            except Exception:
                logger.exception("Analytics tick failed")
            await asyncio.sleep(self.settings.analytics_interval_seconds)

    async def _forecast_loop(self) -> None:
        await asyncio.to_thread(self.model.ready.wait)
        while True:
            try:
                if self.status["seeding"] is None:
                    await asyncio.to_thread(self.analytics.refresh_forecast)
            except Exception:
                logger.exception("Forecast refresh failed")
            await asyncio.sleep(self.settings.forecast_refresh_seconds)

    async def _metrics_loop(self) -> None:
        while True:
            await asyncio.sleep(5)
            if self.hub.client_count:
                await self.hub.broadcast("metrics", self.metrics.snapshot(self.bus.depth() if self.bus else None,
                                                                          self.model))

    # ------------------------------------------------------------------
    def public_status(self) -> dict:
        now = utcnow()
        cfg = self.runtime.get()
        return {
            "brand_name": cfg["brand_name"],
            "model": self.status["model"],
            "model_name": self.model.active_model,
            "seeding": self.status["seeding"],
            "bus": self.bus.name if self.bus else None,
            "sources": cfg["sources"],
            "collectors": {n: c.status() for n, c in self.collectors.items()},
            "simulator": {"enabled": cfg["sources"]["simulator"], "crisis": self.simulator.crisis.to_dict(now)},
            "notification_channels": self.notifier.channels_status(),
            "tunnel": self.tunnel.status(),
            "youtube": {"configured": self.youtube.configured,
                        "channels": [c["title"] for c in self.youtube.list_channels()]},
            "instagram": {"app_configured": self.instagram.app_configured,
                          "accounts": [a["username"] for a in self.instagram.list_accounts()]},
            "simulated_mentions": self.db.scalar("SELECT COUNT(*) FROM mentions WHERE origin = 'simulated'"),
            "mentions_stored": self.db.count_mentions(),
            "websocket_clients": self.hub.client_count,
            "server_time": to_iso(now),
        }

    async def reset_data(self, reseed: bool) -> dict:
        self.db.execute("DELETE FROM mentions")
        self.db.execute("DELETE FROM alerts")
        self.analytics._cache.clear()
        self.analytics.forecast_data = {"computed_at": None}
        self.simulator.stop_crisis()
        seeded = 0
        if reseed:
            seeded = await self.seed_history(self.settings.seed_history_days or 3)
        else:
            await asyncio.to_thread(self.analytics.compute_snapshot)
            await self.hub.broadcast("refresh", {"reason": "reset"})
        return {"seeded": seeded}

    async def sync_instagram(self, ig_user_id: str, force: bool) -> int:
        account = self.db.query("SELECT * FROM instagram_accounts WHERE ig_user_id = ?", (ig_user_id,))
        if not account:
            raise InstagramError("Account not found")
        collector = self.collectors["instagram"]
        try:
            raws = await self.instagram.sync_account(account[0], force)
        except InstagramError as exc:
            self.db.execute("UPDATE instagram_accounts SET last_error=? WHERE ig_user_id=?", (str(exc), ig_user_id))
            raise
        for raw in raws:
            await self.publish(raw)
        collector.last_poll, collector.last_count = time.time(), len(raws)
        collector.total += len(raws)
        return len(raws)

    async def sync_youtube(self, channel_id: str, force: bool) -> int:
        channel = self.db.query("SELECT * FROM youtube_channels WHERE channel_id = ?", (channel_id,))
        if not channel:
            raise YouTubeError("Channel not found")
        collector = self.collectors["youtube"]
        try:
            raws = await self.youtube.sync_channel(channel[0], force)
        except YouTubeError as exc:
            self.db.execute("UPDATE youtube_channels SET last_error=? WHERE channel_id=?", (str(exc), channel_id))
            raise
        for raw in raws:
            await self.publish(raw)
        collector.last_poll, collector.last_count = time.time(), len(raws)
        collector.total += len(raws)
        return len(raws)

    async def use_live_data_only(self, rename_brand: bool) -> dict:
        """Switch off the simulator and delete simulated mentions + alerts."""
        patch = {"sources": {"simulator": False}}
        accounts = self.instagram.list_accounts()
        if accounts:
            patch["sources"]["instagram"] = True
            if rename_brand:
                a = accounts[0]
                patch["brand_name"] = a.get("name") or a["username"]
                patch["keywords"] = sorted({a["username"], f"@{a['username']}", a.get("name") or a["username"]})
        self.runtime.update(patch)
        self.simulator.stop_crisis()
        # let mentions that are still in the queue finish processing, otherwise they
        # would be stored again right after the delete
        for _ in range(20):
            if not self.bus.depth():
                break
            await asyncio.sleep(0.25)
        await asyncio.sleep(1.0)
        deleted = self.db.scalar("SELECT COUNT(*) FROM mentions WHERE origin = 'simulated'")
        self.db.execute("DELETE FROM mentions WHERE origin = 'simulated'")
        self.db.execute("DELETE FROM alerts")
        self.analytics._cache.clear()
        await asyncio.to_thread(self.analytics.refresh_forecast)
        await asyncio.to_thread(self.analytics.compute_snapshot)
        self.wake_collectors()
        await self.hub.broadcast("status", self.public_status())
        await self.hub.broadcast("refresh", {"reason": "live-only"})
        return {"deleted_simulated": deleted, "config": self.runtime.get()}

    def crisis(self, aspect: str, minutes: int, intensity: float) -> dict:
        self.simulator.start_crisis(aspect, minutes, intensity, utcnow())
        return self.simulator.crisis.to_dict(utcnow())

    def recent_window(self, minutes: int):
        return to_iso(utcnow() - timedelta(minutes=minutes))
