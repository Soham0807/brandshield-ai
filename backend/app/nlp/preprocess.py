"""Text preprocessing: noise removal, normalisation, tokenisation, stop-word
removal, lemmatisation, language detection and spam filtering."""

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Optional NLTK support (falls back to built-in rules when data is missing)
# ---------------------------------------------------------------------------
try:
    from nltk.corpus import stopwords as _nltk_stopwords
    from nltk.stem import WordNetLemmatizer

    _NLTK_STOPWORDS = set(_nltk_stopwords.words("english"))
    _LEMMATIZER = WordNetLemmatizer()
    _LEMMATIZER.lemmatize("tests")  # raises LookupError if wordnet is missing
except Exception:  # pragma: no cover - depends on local NLTK data
    _NLTK_STOPWORDS = None
    _LEMMATIZER = None

try:
    from langdetect import DetectorFactory, detect_langs

    DetectorFactory.seed = 0
except Exception:  # pragma: no cover
    detect_langs = None

BUILTIN_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "by", "can", "could", "did", "do", "does", "doing", "down",
    "during", "each", "few", "for", "from", "further", "had", "has", "have",
    "having", "he", "her", "here", "hers", "herself", "him", "himself", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me",
    "more", "most", "my", "myself", "now", "of", "off", "on", "once", "only", "or",
    "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs",
    "them", "themselves", "then", "there", "these", "they", "this", "those",
    "through", "to", "too", "under", "until", "up", "very", "was", "we", "were",
    "what", "when", "where", "which", "while", "who", "whom", "why", "will", "with",
    "would", "you", "your", "yours", "yourself", "yourselves", "also", "got", "get",
    "im", "ive", "u", "ur", "really", "one", "even", "still",
}
# Negations carry sentiment and must never be removed
NEGATIONS = {"no", "not", "nor", "never", "nothing", "don't", "didn't", "isn't",
             "wasn't", "won't", "can't", "couldn't", "nahi", "nahin", "nai"}
# Hinglish / Marathi fillers
REGIONAL_STOPWORDS = {"hai", "tha", "thi", "ka", "ki", "ke", "ko", "se", "aur", "bhi",
                      "ye", "yeh", "wo", "woh", "mein", "me", "hota", "ho", "ahe", "ani",
                      "la", "cha", "chi", "che"}

STOPWORDS = ((_NLTK_STOPWORDS or BUILTIN_STOPWORDS) | REGIONAL_STOPWORDS) - NEGATIONS

# Emojis are converted to words because the tokenizer does not know most of them
EMOJI_WORDS = {
    "😍": " love ", "❤️": " love ", "❤": " love ", "😊": " happy ", "🙂": " good ",
    "😀": " happy ", "😃": " happy ", "😁": " happy ", "👍": " good ", "👌": " perfect ",
    "🔥": " amazing ", "💯": " excellent ", "🥰": " love ", "😋": " delicious ",
    "🤩": " amazing ", "🙌": " great ", "✨": " great ", "😐": " meh ", "🤔": " unsure ",
    "😡": " angry ", "🤬": " furious ", "😠": " angry ", "👎": " bad ", "😞": " disappointed ",
    "😢": " sad ", "😭": " terrible ", "🤮": " disgusting ", "🤢": " disgusting ",
    "💔": " heartbroken ", "😤": " annoyed ", "🙄": " annoying ", "😒": " unhappy ",
}

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
MENTION_RE = re.compile(r"@\w+")
HASHTAG_RE = re.compile(r"#(\w+)")
HTML_RE = re.compile(r"<[^>]+>")
REPEAT_RE = re.compile(r"(.)\1{3,}")
WS_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-zऀ-ॿ]+(?:'[a-z]+)?", re.I)
DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")

SPAM_PATTERNS = [
    r"follow (me|back|us)", r"check (out )?my (profile|page|bio)", r"dm (me|for)",
    r"free followers", r"(buy|get) (cheap )?followers", r"earn \$?\d+", r"work from home",
    r"crypto", r"bitcoin", r"forex", r"giveaway", r"click (the )?link", r"promo code",
    r"link in (my )?bio", r"investment (plan|opportunity)", r"whatsapp me", r"sub4sub",
    r"f4f", r"l4l", r"onlyfans", r"100% guaranteed", r"make money",
]
SPAM_RE = re.compile("|".join(SPAM_PATTERNS), re.I)


@dataclass
class PreparedText:
    original: str
    clean: str          # human readable cleaned text
    model_text: str     # text given to the transformer
    tokens: list[str] = field(default_factory=list)
    lemmas: list[str] = field(default_factory=list)
    language: str = "unknown"
    is_spam: bool = False
    spam_reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "clean": self.clean,
            "model_text": self.model_text,
            "tokens": self.tokens,
            "lemmas": self.lemmas,
            "language": self.language,
            "is_spam": self.is_spam,
            "spam_reason": self.spam_reason,
        }


def _rule_lemmatize(word: str) -> str:
    if len(word) <= 4:
        return word
    for suffix, repl in (("ies", "y"), ("ied", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            stem = word[: -len(suffix)] + repl
            if suffix in ("ing", "ed") and len(stem) > 2 and stem[-1] == stem[-2]:
                stem = stem[:-1]
            return stem
    return word


def lemmatize(word: str) -> str:
    if _LEMMATIZER is not None and word.isascii():
        lemma = _LEMMATIZER.lemmatize(word)
        return _LEMMATIZER.lemmatize(lemma, pos="v") if lemma == word else lemma
    return _rule_lemmatize(word) if word.isascii() else word


def detect_language(text: str) -> str:
    if DEVANAGARI_RE.search(text):
        base = "hi"
    else:
        base = "en"
    if detect_langs is None or len(text) < 12:
        return base
    try:
        best = detect_langs(text)[0]
        if best.prob >= 0.80:
            return best.lang
    except Exception:
        pass
    return base


def detect_spam(original: str, clean: str) -> str | None:
    lowered = original.lower()
    if SPAM_RE.search(lowered):
        return "promotional / scam phrase"
    urls = len(URL_RE.findall(original))
    if urls >= 2:
        return "multiple links"
    if urls and len(clean.split()) <= 4:
        return "link with little content"
    hashtags = len(HASHTAG_RE.findall(original))
    words = max(len(original.split()), 1)
    if hashtags >= 6 and hashtags / words > 0.5:
        return "hashtag stuffing"
    if len(original) > 20 and sum(c.isupper() for c in original if c.isalpha()) / max(
        sum(c.isalpha() for c in original), 1
    ) > 0.85 and urls:
        return "all caps with link"
    if not clean.strip():
        return "no textual content"
    return None


def preprocess(text: str) -> PreparedText:
    original = str(text or "").strip()
    no_html = HTML_RE.sub(" ", original)
    no_urls = URL_RE.sub(" ", no_html)
    no_mentions = MENTION_RE.sub(" ", no_urls)
    no_hashtags = HASHTAG_RE.sub(r"\1", no_mentions)
    squeezed = REPEAT_RE.sub(r"\1\1", no_hashtags)
    clean = WS_RE.sub(" ", squeezed).strip()

    model_text = clean
    for emoji, word in EMOJI_WORDS.items():
        if emoji in model_text:
            model_text = model_text.replace(emoji, word)
    model_text = WS_RE.sub(" ", model_text).strip()

    tokens = [t.lower() for t in TOKEN_RE.findall(model_text)]
    filtered = [t for t in tokens if t not in STOPWORDS and len(t) > 1]
    lemmas = [lemmatize(t) for t in filtered]

    spam_reason = detect_spam(original, clean)
    return PreparedText(
        original=original,
        clean=clean,
        model_text=model_text,
        tokens=tokens,
        lemmas=lemmas,
        language=detect_language(clean) if clean else "unknown",
        is_spam=spam_reason is not None,
        spam_reason=spam_reason,
    )
