"""Hybrid sentiment analysis.

* An ensemble of two transformer models trained on social-media text provides
  contextual understanding: multilingual XLM-RoBERTa and English RoBERTa
  (Cardiff NLP, trained on tweets). Their class probabilities are averaged.
* Neutral's probability is recalibrated (x0.6): the tweet models call many brand
  complaints "neutral".
* A small lexicon of Hinglish / Hindi / Marathi opinion words and English
  brand-risk terms (layoffs, scam, too expensive ...) is blended in, because the
  transformer is weak on romanised Indian languages and reads risk news as fact.
* A confidence-margin rule maps low-confidence predictions to "neutral".

On 200 hand-labelled real comments: 76.0% accuracy (74.0% before the
recalibration, 66.5% for the earlier single DistilBERT model).
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
    "chhan": 0.8, "kadak": 0.8, "jhakaas": 1, "maza aa gaya": 1,
    "बढ़िया": 1, "अच्छा": 0.8, "शानदार": 1, "मस्त": 1, "छान": 0.8, "स्वादिष्ट": 1,
    # Hinglish comparison: "isse acha toh X ka phone hota hai" = "X is better than this" (negative for the brand)
    "acha toh": -1, "accha toh": -1, "achha toh": -1, "se acha": -0.8, "se accha": -0.8, "se achha": -0.8,
}

# English brand-risk vocabulary. Tweet-trained models read these as neutral facts
# ("Zomato lays off 250 employees", "way too expensive"), but for brand monitoring
# they are negative signals.
BRAND_RISK_LEXICON = {
    # business / reputation events in news
    "lays off": -1, "layoff": -1, "layoffs": -1, "lawsuit": -1, "sued": -1, "fraud": -1, "scam": -1,
    "outage": -1, "data breach": -1, "boycott": -1, "recall": -0.8, "fined": -1, "penalty": -0.8,
    "investigation": -0.8, "probe": -0.8, "controversy": -1, "backlash": -1, "shut down": -0.8,
    # price and value complaints
    "too expensive": -0.8, "so expensive": -0.8, "overpriced": -0.8, "too costly": -0.8, "so costly": -0.8,
    "waste of money": -1, "rip off": -1, "ripoff": -1, "hidden charges": -1, "price hike": -0.8,
    "drain the battery": -0.8, "battery drain": -0.8,
}
LEXICON = {**REGIONAL_LEXICON, **BRAND_RISK_LEXICON}

NEGATORS = {"nahi", "nahin", "nai", "nhi", "not", "no", "never", "नहीं", "नाही"}
_WORD_RE = re.compile(r"[\wऀ-ॿ]+", re.U)

NEUTRAL_MARGIN = 0.20   # top-1 minus top-2 probability below this => neutral
LEXICON_WEIGHT = 0.35   # how much a lexicon hit moves the probabilities
# The tweet-trained models put a lot of mass on "neutral" for brand comments that
# people label as opinions; on 200 hand-labelled real comments 40% of negatives
# came out neutral. Neutral's probability is scaled by this before deciding.
NEUTRAL_SCALE = 0.6


def lexicon_terms(text: str) -> list[dict]:
    """Lexicon entries found in the text (same matching rules as lexicon_polarity)."""
    words = _WORD_RE.findall(text.lower())
    joined = f" {' '.join(words)} "
    found, consumed = [], set()
    for term, weight in LEXICON.items():
        if " " not in term or f" {term} " not in joined:
            continue
        found.append({"term": term, "weight": weight, "negated": False})
        parts = term.split()
        for i in range(len(words) - len(parts) + 1):
            if words[i:i + len(parts)] == parts:
                consumed.update(range(i, i + len(parts)))
    for i, w in enumerate(words):
        weight = LEXICON.get(w)
        if i in consumed or weight is None:
            continue
        negated = any(n in NEGATORS for n in words[max(0, i - 2): i + 3] if n != w)
        found.append({"term": w, "weight": -weight if negated else weight, "negated": negated})
    return found


def explain(model: "SentimentModel", text: str, max_words: int = 40) -> dict:
    """Word importance by occlusion: drop each word, re-score, and measure how
    far the sentiment score (positive minus negative) moves. A positive impact
    means the word pushed the prediction towards positive."""
    words = text.split()
    base = model.predict([text])[0]
    impacts = []
    if 1 < len(words) <= max_words:
        variants = [" ".join(words[:i] + words[i + 1:]) for i in range(len(words))]
        for word, pred in zip(words, model.predict(variants)):
            impact = base["score"] - pred["score"]
            if abs(impact) >= 0.02:
                impacts.append({"word": word, "impact": round(impact, 3)})
        impacts.sort(key=lambda d: abs(d["impact"]), reverse=True)
    return {"words": impacts[:8], "lexicon": lexicon_terms(text), "neutral_scale": NEUTRAL_SCALE,
            "too_long": len(words) > max_words}


def lexicon_polarity(text: str) -> float | None:
    words = _WORD_RE.findall(text.lower())
    joined = f" {' '.join(words)} "
    total, hits = 0.0, 0
    consumed: set[int] = set()  # word positions covered by a matched phrase
    # phrases first, so "acha toh" overrides the single word "acha" inside it
    for term, weight in LEXICON.items():
        if " " not in term or f" {term} " not in joined:
            continue
        total += weight
        hits += 1
        parts = term.split()
        for i in range(len(words) - len(parts) + 1):
            if words[i:i + len(parts)] == parts:
                consumed.update(range(i, i + len(parts)))
    for i, w in enumerate(words):
        if i in consumed:
            continue
        weight = LEXICON.get(w)
        if weight is None or " " in w:
            continue
        negated = any(n in NEGATORS for n in words[max(0, i - 2): i + 3] if n != w)
        total += -weight if negated else weight
        hits += 1
    if not hits:
        return None
    return max(-1.0, min(1.0, total / hits))


class SentimentModel:
    def __init__(self, model_name: str, fallback_model: str, batch_size: int = 32,
                 max_length: int = 256, cache_size: int = 50_000):
        # both may be comma-separated: the primary list is an ensemble (all members used),
        # the fallback list is tried in order and the first model that loads is used alone
        self.model_name = model_name
        self.fallback_model = fallback_model
        self.model_names = [m.strip() for m in model_name.split(",") if m.strip()]
        self.fallback_names = [m.strip() for m in fallback_model.split(",") if m.strip()]
        self._pipes: list[tuple[str, object, bool]] = []  # (name, pipeline, binary)
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

        def try_load(name):
            try:
                logger.info("Loading sentiment model %s ...", name)
                pipe = pipeline("text-classification", model=name, top_k=None)
                binary = getattr(pipe.model.config, "num_labels", 3) == 2
                return name, pipe, binary
            except Exception as exc:  # pragma: no cover - network / disk issues
                self.load_error = f"{name}: {exc}"
                logger.exception("Could not load %s", name)
                return None

        # every ensemble member that loads is used; if none does, the first fallback that loads
        pipes = [p for p in map(try_load, self.model_names) if p]
        if not pipes:
            for name in self.fallback_names:
                loaded = try_load(name)
                if loaded:
                    pipes = [loaded]
                    break
        if not pipes:
            raise RuntimeError(f"No sentiment model could be loaded ({self.load_error})")
        self._pipes = pipes
        self._pipe = pipes[0][1]
        self.binary = all(b for _, _, b in pipes)
        self.active_model = " + ".join(name for name, _, _ in pipes)
        if len(pipes) < len(self.model_names):
            logger.warning("Sentiment ensemble running with %s of %s models", len(pipes), len(self.model_names))
        logger.info("Sentiment model ready: %s", self.active_model)
        self.ready.set()

    @property
    def avg_inference_ms(self) -> float:
        if not self.total_inferences:
            return 0.0
        return 1000 * self.total_inference_seconds / self.total_inferences

    # ------------------------------------------------------------------
    @staticmethod
    def _to_three_classes(out, binary: bool) -> dict[str, float]:
        scores = out if isinstance(out, list) else [out]
        probs: dict[str, float] = {}
        for s in scores:
            # 5-class models ("Very Negative" ... "Very Positive") are folded into 3 classes
            label = LABEL_ALIASES.get(s["label"].lower(), s["label"].lower().replace("very ", ""))
            probs[label] = probs.get(label, 0.0) + float(s["score"])
        if binary:
            pos, neg = probs.get("positive", 0.0), probs.get("negative", 0.0)
            neutral = max(0.0, 1.0 - abs(pos - neg) * 1.4)
            total = pos + neg + neutral
            probs = {"positive": pos / total, "neutral": neutral / total, "negative": neg / total}
        return {label: probs.get(label, 0.0) for label in LABELS}

    def _raw_predict(self, texts: list[str]) -> list[dict[str, float]]:
        """Class probabilities averaged over every model in the ensemble."""
        with self._lock:
            start = time.perf_counter()
            per_model = []
            for _name, pipe, binary in self._pipes:
                outputs = pipe(texts, batch_size=self.batch_size, truncation=True, max_length=self.max_length)
                per_model.append([self._to_three_classes(out, binary) for out in outputs])
            elapsed = time.perf_counter() - start
        self.total_inferences += len(texts)
        self.total_inference_seconds += elapsed
        n = len(per_model)
        return [{label: sum(m[i][label] for m in per_model) / n for label in LABELS} for i in range(len(texts))]

    @staticmethod
    def _finalise(text: str, probs: dict[str, float]) -> dict:
        probs = dict(probs)
        probs["neutral"] *= NEUTRAL_SCALE
        total = sum(probs.values()) or 1.0
        probs = {k: v / total for k, v in probs.items()}
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
