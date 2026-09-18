"""Live pipeline performance metrics (throughput, latency, inference time)."""

import threading
import time
from collections import deque

import numpy as np


class PipelineMetrics:
    def __init__(self):
        self._lock = threading.Lock()
        self.started = time.time()
        self.ingested = 0
        self.processed = 0
        self.stored = 0
        self.duplicates = 0
        self.errors = 0
        self.batches = 0
        self._processed_events: deque = deque()  # (timestamp, count)
        self._latency_ms: deque = deque(maxlen=2000)      # ingest -> stored
        self._batch_ms_per_item: deque = deque(maxlen=500)
        self._labelled: deque = deque(maxlen=5000)        # (true, predicted) from simulator
        self.last_error: str | None = None

    def record_ingested(self, n: int = 1) -> None:
        with self._lock:
            self.ingested += n

    def record_batch(self, size: int, stored: int, batch_seconds: float, latencies_ms: list[float],
                     labelled: list[tuple[str, str]]) -> None:
        now = time.time()
        with self._lock:
            self.processed += size
            self.stored += stored
            self.duplicates += size - stored
            self.batches += 1
            self._processed_events.append((now, size))
            self._latency_ms.extend(latencies_ms)
            if size:
                self._batch_ms_per_item.append(1000 * batch_seconds / size)
            self._labelled.extend(labelled)
            while self._processed_events and self._processed_events[0][0] < now - 60:
                self._processed_events.popleft()

    def record_error(self, message: str) -> None:
        with self._lock:
            self.errors += 1
            self.last_error = message

    def snapshot(self, queue_depth: int | None, model) -> dict:
        now = time.time()
        with self._lock:
            while self._processed_events and self._processed_events[0][0] < now - 60:
                self._processed_events.popleft()
            window = min(60.0, max(now - self.started, 1.0))
            per_min = sum(c for _, c in self._processed_events)
            latencies = np.array(self._latency_ms) if self._latency_ms else None
            per_item = np.array(self._batch_ms_per_item) if self._batch_ms_per_item else None
            labelled = list(self._labelled)
            data = {
                "uptime_seconds": int(now - self.started),
                "ingested_total": self.ingested,
                "processed_total": self.processed,
                "stored_total": self.stored,
                "duplicates_total": self.duplicates,
                "errors_total": self.errors,
                "last_error": self.last_error,
                "batches_total": self.batches,
                "throughput_per_sec": round(per_min / window, 2),
                "processed_last_minute": per_min,
                "queue_depth": queue_depth,
                "latency_ms": {
                    "avg": round(float(latencies.mean()), 1) if latencies is not None else None,
                    "p50": round(float(np.percentile(latencies, 50)), 1) if latencies is not None else None,
                    "p95": round(float(np.percentile(latencies, 95)), 1) if latencies is not None else None,
                    "max": round(float(latencies.max()), 1) if latencies is not None else None,
                },
                "processing_ms_per_item": round(float(per_item.mean()), 2) if per_item is not None else None,
                "model": {
                    "name": model.active_model,
                    "ready": model.ready.is_set(),
                    "avg_inference_ms_per_text": round(model.avg_inference_ms, 2),
                    "texts_inferred": model.total_inferences,
                    "load_error": model.load_error if not model.ready.is_set() else None,
                },
            }
        if labelled:
            correct = sum(1 for t, p in labelled if t == p)
            data["live_agreement"] = {"samples": len(labelled), "accuracy": round(correct / len(labelled), 4)}
        else:
            data["live_agreement"] = None
        return data
