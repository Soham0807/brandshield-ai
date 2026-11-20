"""Unit tests for aspect extraction and the regional-language lexicon."""

from app.nlp.aspects import AspectExtractor, split_clauses
from app.nlp.sentiment import lexicon_polarity


def test_aspects_found_in_mixed_review():
    found = AspectExtractor().find("the delivery was late and the price is too expensive")
    assert "delivery" in found
    assert "price" in found


def test_no_aspect_in_unrelated_text():
    assert AspectExtractor().find("hello there how are you") == []


def test_clauses_are_split_on_contrast_words():
    clauses = split_clauses("The coffee was great but the staff were rude")
    assert len(clauses) >= 2


def test_extract_clauses_maps_each_aspect_to_its_own_clause():
    mapping = AspectExtractor().extract_clauses("The coffee was great but the staff were rude")
    assert "food_quality" in mapping and "service" in mapping
    assert any("coffee" in c for c in mapping["food_quality"])
    assert any("staff" in c for c in mapping["service"])


def test_custom_aspects_can_be_configured():
    ex = AspectExtractor({"parking": ["parking", "car park"]})
    assert ex.names == ["parking"]
    assert ex.find("no parking near the cafe") == ["parking"]


def test_lexicon_returns_none_without_regional_words():
    assert lexicon_polarity("zzz qqq") is None


def test_hinglish_comparison_idiom_is_negative_for_the_brand():
    # "isse acha toh infinix ka phone hota hai" = "Infinix is better than this"
    assert lexicon_polarity("isse acha toh infinix ka phone hota hai") < 0
    # plain praise still positive
    assert lexicon_polarity("phone bahut acha hai") > 0


def test_brand_risk_news_and_price_complaints_are_negative():
    assert lexicon_polarity("Zomato lays off 250 employees") < 0
    assert lexicon_polarity("Way too expensive for what it offers") < 0
    assert lexicon_polarity("this is a scam") < 0


def test_negated_risk_term_flips():
    assert lexicon_polarity("this is not a scam") > 0


def test_neutral_is_recalibrated_before_deciding():
    from app.nlp.sentiment import SentimentModel
    # model slightly prefers neutral over a clear negative lean -> negative after recalibration
    # (before recalibration negative led by only 0.05 and the margin rule made it neutral)
    out = SentimentModel._finalise("battery life could be better", {"positive": 0.05, "neutral": 0.45, "negative": 0.50})
    assert out["label"] == "negative"
    # a genuinely neutral text stays neutral
    out = SentimentModel._finalise("the event starts at 5 pm", {"positive": 0.1, "neutral": 0.85, "negative": 0.05})
    assert out["label"] == "neutral"


def test_lexicon_scores_hinglish_praise_above_complaint():
    good = lexicon_polarity("khana bahut accha tha")
    bad = lexicon_polarity("khana bekar tha")
    assert good is not None and bad is not None
    assert good > bad
