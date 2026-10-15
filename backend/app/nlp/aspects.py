"""Aspect-based sentiment analysis (ABSA).

1. Split a mention into clauses ("food was great but delivery was late").
2. Detect aspects in each clause with a configurable keyword lexicon
   (whole-word matching, so "late" does not match "chocolate").
3. Classify each aspect clause with the sentiment model, so every aspect
   gets its own polarity.
"""

import re

DEFAULT_ASPECTS: dict[str, list[str]] = {
    "food_quality": ["food", "taste", "tasty", "coffee", "cappuccino", "latte", "tea", "chai",
                     "dish", "meal", "burger", "pizza", "sandwich", "dessert", "cake", "stale",
                     "fresh", "flavour", "flavor", "delicious", "bland", "undercooked", "khana",
                     "swad", "portion", "menu", "brew", "pastry", "croissant", "waffle"],
    "service": ["service", "staff", "waiter", "waitress", "barista", "rude", "manager",
                "employee", "behaviour", "behavior", "attitude", "waited", "waiting",
                "ignored", "polite", "helpful", "hospitality", "server"],
    "delivery": ["delivery", "delivered", "deliver", "arrived", "late", "delayed", "delay",
                 "zomato", "swiggy", "rider", "courier", "shipping", "never arrived",
                 "wrong order", "missing item", "on time"],
    "price": ["price", "prices", "pricing", "expensive", "overpriced", "cheap", "costly",
              "cost", "value for money", "worth", "bill", "affordable", "mehenga", "mehnga",
              "paisa", "discount"],
    "ambience": ["ambience", "ambiance", "atmosphere", "vibe", "vibes", "music", "seating",
                 "decor", "interior", "crowded", "noisy", "cozy", "cosy", "aesthetic", "view"],
    "hygiene": ["hygiene", "dirty", "clean", "cleanliness", "hair", "cockroach", "insect",
                "smell", "washroom", "unhygienic", "food poisoning", "sick", "fly", "flies"],
    "app_experience": ["app", "website", "online order", "payment", "upi", "checkout", "crash",
                       "crashed", "login", "coupon", "refund", "promo", "loyalty"],
    "packaging": ["packaging", "packed", "package", "container", "spilled", "spilt", "leaked",
                  "leaking", "box", "lid"],
}

GENERAL_ASPECTS: dict[str, list[str]] = {
    "product": ["product", "products", "design", "feature", "features", "model", "version", "update",
                "launch", "release", "camera", "screen", "display", "battery", "size", "colour", "color"],
    "quality": ["quality", "broken", "broke", "defective", "faulty", "damaged", "durable", "build",
                "material", "cheap quality", "stopped working", "doesn't work", "not working", "original"],
    "price": ["price", "prices", "pricing", "expensive", "overpriced", "cheap", "costly", "cost",
              "value for money", "worth", "affordable", "discount", "offer", "sale", "mehenga", "mehnga", "paisa"],
    "customer_support": ["support", "customer service", "customer care", "customer support", "helpline",
                         "complaint", "complaints", "refund", "return", "replacement", "warranty", "response",
                         "respond", "responding", "agent", "ticket", "no reply", "service"],
    "delivery": ["delivery", "delivered", "deliver", "shipping", "shipped", "courier", "late", "delayed",
                 "delay", "arrived", "never arrived", "tracking", "wrong order", "missing item", "on time"],
    "app_experience": ["app", "website", "online", "login", "payment", "upi", "checkout", "crash", "crashed",
                       "glitch", "bug", "bugs", "slow", "loading", "account", "notification", "ios", "android"],
    "trust": ["trust", "scam", "fraud", "cheated", "lied", "lies", "fake", "misleading", "boycott",
              "privacy", "ethics", "unethical", "reputation"],
    "marketing": ["ad", "ads", "advert", "advertisement", "campaign", "collab", "influencer", "giveaway",
                  "contest", "reel", "content", "meme", "brand ambassador"],
}

TECH_ASPECTS: dict[str, list[str]] = {
    "performance": ["performance", "fast", "speed", "slow", "lag", "laggy", "smooth", "processor", "chip",
                    "heating", "overheating", "hang", "hangs"],
    "battery": ["battery", "charge", "charging", "charger", "drain", "drains", "backup", "battery life"],
    "camera": ["camera", "photo", "photos", "video", "selfie", "lens", "zoom"],
    "design": ["design", "look", "looks", "colour", "color", "size", "weight", "build", "premium", "notch"],
    "software": ["software", "update", "ios", "android", "os", "bug", "bugs", "glitch", "feature", "features", "ai"],
    "price": ["price", "expensive", "overpriced", "cheap", "costly", "worth", "value for money",
              "affordable", "discount", "mehenga"],
    "customer_support": ["support", "customer service", "customer care", "service center", "repair",
                         "warranty", "refund", "replacement", "complaint"],
    "competition": ["samsung", "google", "pixel", "xiaomi", "oneplus", "apple", "iphone", "android",
                    "copy", "copied", "better than", "worse than"],
}

ASPECT_PRESETS: dict[str, dict] = {
    "general": {"label": "General brand", "aspects": GENERAL_ASPECTS},
    "tech": {"label": "Tech / gadget brand", "aspects": TECH_ASPECTS},
    "cafe": {"label": "Café & restaurant", "aspects": DEFAULT_ASPECTS},
}

CLAUSE_SPLIT_RE = re.compile(
    r"[.!?;\n]+|\b(?:but|however|although|though|whereas|except|lekin|magar|par|pan)\b",
    re.I,
)


def split_clauses(text: str) -> list[str]:
    parts = [p.strip(" ,-") for p in CLAUSE_SPLIT_RE.split(text or "")]
    return [p for p in parts if len(p.split()) >= 2]


class AspectExtractor:
    def __init__(self, aspects: dict[str, list[str]] | None = None):
        self.update(aspects or DEFAULT_ASPECTS)

    def update(self, aspects: dict[str, list[str]]) -> None:
        compiled = {}
        for aspect, words in aspects.items():
            words = [w for w in words if w]
            if not words:
                continue
            ascii_words = [re.escape(w) for w in words if w.isascii()]
            other_words = [w for w in words if not w.isascii()]
            pattern = re.compile(r"\b(?:" + "|".join(ascii_words) + r")\b", re.I) if ascii_words else None
            compiled[aspect] = (pattern, other_words)
        self._compiled = compiled

    @property
    def names(self) -> list[str]:
        return list(self._compiled)

    def find(self, text: str) -> list[str]:
        found = []
        for aspect, (pattern, other_words) in self._compiled.items():
            if (pattern and pattern.search(text)) or any(w in text for w in other_words):
                found.append(aspect)
        return found

    def extract_clauses(self, text: str) -> dict[str, list[str]]:
        """Map aspect -> clauses that mention it."""
        clauses = split_clauses(text) or [text]
        mapping: dict[str, list[str]] = {}
        for clause in clauses:
            for aspect in self.find(clause):
                mapping.setdefault(aspect, []).append(clause)
        if not mapping:
            for aspect in self.find(text):
                mapping.setdefault(aspect, []).append(text)
        return mapping

    def analyze_batch(self, texts: list[str], overall: list[dict], model) -> list[list[dict]]:
        """Return per-mention aspect sentiments, running the model once on all clauses."""
        per_text = [self.extract_clauses(t) for t in texts]
        clause_texts: list[str] = []
        for text, mapping in zip(texts, per_text):
            clauses = {c for cs in mapping.values() for c in cs}
            if len(clauses) > 1 or (clauses and next(iter(clauses)) != text):
                clause_texts.extend(clauses)
        clause_results = dict(zip(clause_texts, model.predict(clause_texts))) if clause_texts else {}

        results = []
        for text, mapping, whole in zip(texts, per_text, overall):
            items = []
            for aspect, clauses in mapping.items():
                preds = [clause_results.get(c, whole) for c in clauses]
                score = sum(p["score"] for p in preds) / len(preds)
                label = max(preds, key=lambda p: abs(p["score"]))["label"] if len(preds) > 1 else preds[0]["label"]
                items.append({
                    "aspect": aspect,
                    "sentiment": label,
                    "score": round(score, 4),
                    "evidence": clauses[0][:160],
                })
            results.append(items)
        return results
