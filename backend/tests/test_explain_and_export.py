"""Unit tests for the prediction explanation and the CSV export helpers."""

from app.api.routes import _csv_cell
from app.nlp.sentiment import explain, lexicon_terms


def test_lexicon_terms_lists_phrase_not_inner_word():
    terms = {t["term"]: t for t in lexicon_terms("isse acha toh infinix ka phone hota hai")}
    assert "acha toh" in terms and terms["acha toh"]["weight"] < 0
    assert "acha" not in terms


def test_lexicon_terms_marks_negation():
    terms = lexicon_terms("khana accha nahi tha")
    assert terms == [{"term": "accha", "weight": -0.8, "negated": True}]


class FakeModel:
    """Score = +1 per 'good', -1 per 'bad' (clipped), enough to test occlusion."""

    def predict(self, texts):
        out = []
        for t in texts:
            words = t.split()
            s = max(-1.0, min(1.0, 0.5 * words.count("good") - 0.5 * words.count("bad")))
            out.append({"score": s})
        return out


def test_explain_ranks_words_by_impact():
    ex = explain(FakeModel(), "the food was bad")
    assert ex["words"] == [{"word": "bad", "impact": -0.5}]


def test_explain_skips_long_text():
    ex = explain(FakeModel(), " ".join(["word"] * 50), max_words=40)
    assert ex["words"] == [] and ex["too_long"]


def test_csv_cell_neutralises_formulas():
    assert _csv_cell("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert _csv_cell("normal text") == "normal text"
    assert _csv_cell(0.5) == 0.5
