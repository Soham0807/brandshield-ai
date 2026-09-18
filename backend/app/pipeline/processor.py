"""Stream processor: raw mention -> preprocessing -> sentiment -> aspects -> storage."""

import asyncio
import hashlib
import json
import logging
import time

from app.db import Database, decode_mention, parse_any_datetime, to_iso, utcnow
from app.nlp.aspects import AspectExtractor
from app.nlp.preprocess import preprocess
from app.nlp.sentiment import SentimentModel
from app.pipeline.metrics import PipelineMetrics

logger = logging.getLogger("brandshield.processor")


def mention_id(source: str, external_id: str) -> str:
    return hashlib.sha1(f"{source}:{external_id}".encode("utf-8")).hexdigest()[:24]


def normalise_raw(raw: dict) -> dict:
    """Fill defaults so every collector / API client can send minimal payloads."""
    text = str(raw.get("text") or "").strip()
    source = str(raw.get("source") or "api").lower()
    external_id = str(raw.get("external_id") or hashlib.sha1(
        f"{text}|{raw.get('author')}|{raw.get('created_at')}".encode("utf-8")).hexdigest())
    created = parse_any_datetime(raw.get("created_at"))
    now = utcnow()
    if created > now:
        created = now
    return {
        "id": raw.get("id") or mention_id(source, external_id),
        "source": source,
        "external_id": external_id,
        "author": raw.get("author"),
        "text": text,
        "url": raw.get("url"),
        "created_at": to_iso(created),
        "ingested_at": raw.get("ingested_at") or to_iso(now),
        "_ingested_monotonic": raw.get("_ingested_monotonic"),
        "engagement": int(raw.get("engagement") or 0),
        "true_label": raw.get("true_label"),
        "origin": raw.get("origin") or "live",
        "parent_id": raw.get("parent_id"),
    }


class Processor:
    def __init__(self, db: Database, model: SentimentModel, aspects: AspectExtractor,
                 metrics: PipelineMetrics, on_processed=None):
        self.db = db
        self.model = model
        self.aspects = aspects
        self.metrics = metrics
        self.on_processed = on_processed  # async callback(list[dict])

    def analyze(self, raws: list[dict]) -> list[dict]:
        """Synchronous, CPU bound: run the NLP pipeline over a batch."""
        prepared = [preprocess(r["text"]) for r in raws]
        texts = [p.model_text for p in prepared]
        sentiments = self.model.predict(texts)
        aspect_lists = self.aspects.analyze_batch(texts, sentiments, self.model)
        processed_at = to_iso(utcnow())
        rows = []
        for raw, prep, sent, aspects in zip(raws, prepared, sentiments, aspect_lists):
            rows.append({
                "id": raw["id"],
                "source": raw["source"],
                "external_id": raw["external_id"],
                "author": raw.get("author"),
                "text": raw["text"],
                "clean_text": prep.clean,
                "keywords": " ".join(prep.lemmas),
                "url": raw.get("url"),
                "language": prep.language,
                "created_at": raw["created_at"],
                "ingested_at": raw["ingested_at"],
                "processed_at": processed_at,
                "sentiment": sent["label"],
                "confidence": sent["confidence"],
                "score": sent["score"],
                "probs": json.dumps(sent["probs"]),
                "aspects": json.dumps(aspects),
                "is_spam": int(prep.is_spam),
                "spam_reason": prep.spam_reason,
                "engagement": raw.get("engagement", 0),
                "true_label": raw.get("true_label"),
                "origin": raw["origin"],
                "parent_id": raw.get("parent_id"),
            })
        return rows

    async def process_batch(self, messages: list[dict], broadcast: bool = True) -> list[dict]:
        start = time.perf_counter()
        raws = [normalise_raw(m) for m in messages if str(m.get("text") or "").strip()]
        # de-duplicate within the batch and against the database
        unique = {r["id"]: r for r in raws}
        existing = self.db.existing_ids(list(unique))
        fresh = [r for rid, r in unique.items() if rid not in existing]
        rows = await asyncio.to_thread(self.analyze, fresh) if fresh else []
        stored = await asyncio.to_thread(self.db.insert_mentions, rows)
        elapsed = time.perf_counter() - start
        now_mono = time.monotonic()
        latencies = [1000 * (now_mono - r["_ingested_monotonic"]) for r in fresh if r.get("_ingested_monotonic")]
        labelled = [(r["true_label"], row["sentiment"]) for r, row in zip(fresh, rows)
                    if r.get("true_label") and not row["is_spam"]]
        self.metrics.record_batch(len(messages), stored, elapsed, latencies, labelled)
        decoded = [decode_mention(row) for row in rows]
        if broadcast and decoded and self.on_processed:
            await self.on_processed(decoded)
        return decoded

    async def run(self, bus) -> None:
        await asyncio.to_thread(self.model.ready.wait)
        logger.info("Processor started on %s bus", bus.name)
        async for batch in bus.batches(max_batch=32, max_wait=0.5):
            try:
                await self.process_batch(batch)
            except Exception as exc:  # keep the stream alive
                logger.exception("Batch failed")
                self.metrics.record_error(str(exc))
