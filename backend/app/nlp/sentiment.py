"""Hybrid sentiment analysis.

* Multilingual DistilBERT provides contextual understanding.
* A small lexicon of Hinglish / Hindi / Marathi opinion words is blended in,
  because the transformer is weak on romanised Indian languages.
* A confidence-margin rule maps low-confidence predictions to "neutral".
"""

import logging
import re
import threading
import time
from collections import OrderedDict

logger = logging.getLogger("brandshield.sentiment")

LABELS = ("positive", "neutral", "negative")
LABEL_ALIASES = {"label_0": "negative", "label_1": "neutral", "label_2": "positive",
                 "neg": "negative", "neu": "neutral", "pos": "positive"}

REGIONAL_LEXICON = {
    # negative
    "bekar": -1, "bekaar": -1, "bakwas": -1, "bakwaas": -1, "ghatiya": -1, "kharab": -1,
    "kharaab": -1, "faltu": -1, "bura": -1, "buri": -1, "ganda": -1, "gandi": -1,
    "mehenga": -0.6, "mehnga": -0.6, "thanda": -0.4, "vait": -1, "wait kela": -0.6,
    "bekar hai": -1, "pakau": -0.8, "chindi": -0.8, "lootere": -1, "loot": -0.8,
    "बेकार": -1, "खराब": -1, "घटिया": -1, "बकवास": -1, "महंगा": -0.6, "वाईट": -1,
    # positive
    "mast": 1, "badhiya": 1, "badiya": 1, "accha": 0.8, "achha": 0.8, "acha": 0.8,
    "zabardast": 1, "shandaar": 1, "lajawab": 1, "swadisht": 1, "bhari": 1, "chan": 0.8,
    "chhan": 0.8, "ekdum": 0.3, "kadak": 0.8, "jhakaas": 1, "maza aa gaya": 1,
    "बढ़िया": 1, "अच्छा": 0.8, "शानदार": 1, "मस्त": 1, "छान": 0.8, "स्वादिष्ट": 1,
}
NEGATORS = {"nahi", "nahin", "nai", "not", "no", "never", "नहीं", "नाही"}
_WORD_RE = re.compile(r"[\wऀ-ॿ]+", re.U)

NEUTRAL_MARGIN = 0.20   # top-1 minus top-2 probability below this => neutral
LEXICON_WEIGHT = 0.35   # how much a lexicon hit moves the probabilities


def lexicon_polarity(text: str) -> float | None:
    words = _WORD_RE.findall(text.lower())
    joined = " ".join(words)
    total, hits = 0.0, 0
    for term, weight in REGIONAL_LEXICON.items():
        if " " in term:
            if term in joined:
                total += weight
                hits += 1
            continue
        for i, w in enumerate(words):
            if w == term:
                negated = any(n in NEGATORS for n in words[max(0, i - 2): i + 3] if n != w)
                total += -weight if negated else weight
                hits += 1
    if not hits:
        return None
    return max(-1.0, min(1.0, total / hits))


class SentimentModel:
    def __init__(self, model_name: str, fallback_model: str, batch_size: int = 32,
                 max_length: int = 256, cache_size: int = 50_000):
        self.model_name = model_name
        self.fallback_model = fallback_model
        self.batch_size = batch_size
        self.max_length = max_length
        self.active_model: str | None = None
        self.binary = False
        self.ready = threading.Event()
        self.load_error: str | None = None
        self._pipe = None
        self._lock = threading.Lock()
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._cache_size = cache_size
        self.total_inferences = 0
        self.total_inference_seconds = 0.0

    # ------------------------------------------------------------------
    def load(self) -> None:
        from transformers import pipeline

        for name, binary in ((self.model_name, False), (self.fallback_model, True)):
            try:
                logger.info("Loading sentiment model %s ...", name)
                self._pipe = pipeline("text-classification", model=name, top_k=None)
                self.active_model = name
                self.binary = binary
                logger.info("Sentiment model ready: %s", name)
                break
            except Exception as exc:  # pragma: no cover - network / disk issues
                self.load_error = f"{name}: {exc}"
                logger.exception("Could not load %s", name)
        if self._pipe is None:
            raise RuntimeError(f"No sentiment model could be loaded ({self.load_error})")
        self.ready.set()

    @property
    def avg_inference_ms(self) -> float:
        if not self.total_inferences:
            return 0.0
        return 1000 * self.total_inference_seconds / self.total_inferences

    # ------------------------------------------------------------------
    def _raw_predict(self, texts: list[str]) -> list[dict[str, float]]:
        with self._lock:
            start = time.perf_counter()
            outputs = self._pipe(texts, batch_size=self.batch_size, truncation=True,
                                 max_length=self.max_length)
            elapsed = time.perf_counter() - start
        self.total_inferences += len(texts)
        self.total_inference_seconds += elapsed
        results = []
        for out in outputs:
            scores = out if isinstance(out, list) else [out]
            probs: dict[str, float] = {}
            for s in scores:
                # 5-class models ("Very Negative" ... "Very Positive") are folded into 3 classes
                label = LABEL_ALIASES.get(s["label"].lower(), s["label"].lower().replace("very ", ""))
                probs[label] = probs.get(label, 0.0) + float(s["score"])
            if self.binary:
                pos, neg = probs.get("positive", 0.0), probs.get("negative", 0.0)
                neutral = max(0.0, 1.0 - abs(pos - neg) * 1.4)
                total = pos + neg + neutral
                probs = {"positive": pos / total, "neutral": neutral / total, "negative": neg / total}
            results.append({label: probs.get(label, 0.0) for label in LABELS})
        return results

    @staticmethod
    def _finalise(text: str, probs: dict[str, float]) -> dict:
        probs = dict(probs)
        polarity = lexicon_polarity(text)
        if polarity is not None:
            target = {
                "positive": max(polarity, 0.0),
                "negative": max(-polarity, 0.0),
                "neutral": 1.0 - abs(polarity),
            }
            probs = {k: (1 - LEXICON_WEIGHT) * probs[k] + LEXICON_WEIGHT * target[k] for k in LABELS}

        ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
        label, confidence = ranked[0]
        if label != "neutral" and confidence - ranked[1][1] < NEUTRAL_MARGIN and polarity is None:
            label = "neutral"
            confidence = max(probs["neutral"], 1 - abs(probs["positive"] - probs["negative"]))
        return {
            "label": label,
            "confidence": round(float(confidence), 4),
            "score": round(float(probs["positive"] - probs["negative"]), 4),
            "probs": {k: round(float(v), 4) for k, v in probs.items()},
            "lexicon_polarity": polarity,
        }

    def predict(self, texts: list[str]) -> list[dict]:
        """Classify texts. Results are cached because social media is full of
        duplicates and the same aspect clauses appear again and again."""
        if not self.ready.is_set():
            self.ready.wait()
        keys = [(t or "").strip()[:2000] for t in texts]
        missing = []
        for key in keys:
            if key and key not in self._cache and key not in missing:
                missing.append(key)
        if missing:
            for key, probs in zip(missing, self._raw_predict(missing)):
                self._cache[key] = self._finalise(key, probs)
                if len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
        neutral = {"label": "neutral", "confidence": 1.0, "score": 0.0,
                   "probs": {"positive": 0.0, "neutral": 1.0, "negative": 0.0},
                   "lexicon_polarity": None}
        return [dict(self._cache[k]) if k else dict(neutral) for k in keys]
