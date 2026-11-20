"""Unit tests for the text preprocessing stage (cleaning, tokens, language, spam)."""

from app.nlp.preprocess import detect_language, preprocess


def test_urls_and_mentions_are_removed_from_clean_text():
    out = preprocess("Loved the coffee @saffron_cafe https://example.com/promo")
    assert "https://" not in out.clean
    assert "coffee" in out.clean.lower()


def test_tokens_and_lemmas_are_produced():
    out = preprocess("The waiters were ignoring us for minutes")
    assert out.tokens, "expected tokens"
    # stopwords are dropped from lemmas; content words are reduced to their base form
    assert "waiter" in out.lemmas and "ignore" in out.lemmas and "minute" in out.lemmas
    assert "the" not in out.lemmas


def test_short_words_are_not_mangled_by_lemmatizer():
    from app.nlp.preprocess import lemmatize
    assert lemmatize("us") == "us"
    assert lemmatize("was") == "was"


def test_english_is_detected():
    assert detect_language("The food was really good and the staff were friendly") == "en"


def test_devanagari_is_not_detected_as_english():
    assert detect_language("खाना बहुत अच्छा था") != "en"


def test_promotional_spam_is_flagged():
    out = preprocess("Click here to WIN FREE followers!!! visit http://spam.example now buy now buy now")
    assert out.is_spam
    assert out.spam_reason


def test_normal_review_is_not_spam():
    out = preprocess("Delivery was late by 40 minutes and the pizza arrived cold.")
    assert not out.is_spam


def test_empty_text_does_not_crash():
    out = preprocess("")
    assert out.clean == ""


def test_to_dict_exposes_pipeline_fields():
    d = preprocess("Great service").to_dict()
    for key in ("original", "clean", "model_text", "tokens", "lemmas", "language"):
        assert key in d
