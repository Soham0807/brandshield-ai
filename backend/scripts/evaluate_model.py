"""Evaluate the sentiment model and aspect extractor.

Reports accuracy, precision, recall, F1 (macro + per class), confusion matrix
and inference time, for:

* ``domain``    - hand-labelled brand comments incl. Hinglish / Hindi / Marathi
                  (backend/eval/domain_labeled.csv), written by the team
* ``real``      - 200 real collected comments (110 YouTube, 60 Instagram, 30 news),
                  sampled at random from the live database and labelled by hand
                  (backend/eval/real_comments_labeled.csv)
* ``appstore``  - App Store reviews collected by the live system, labelled by the
                  reviewer's own star rating (1-2 negative, 3 neutral, 4-5 positive)
* ``tweet_eval`` - public TweetEval sentiment benchmark (test split, downloaded
                  from the Hugging Face Hub, ~12k tweets; use --limit)

It also compares the raw model output (the averaged ensemble) against the
hybrid model (ensemble + regional lexicon + neutral margin) as an ablation study.

Besides 3-class accuracy it reports polarity accuracy: of the comments that are truly
positive or negative and that the model labels positive or negative, the share it gets
right (i.e. how often it confuses praise with a complaint). ``coverage`` is the share of
truly polar comments the model labels polar rather than neutral.

Usage (from the backend folder):
    python -m scripts.evaluate_model
    python -m scripts.evaluate_model --datasets domain real tweet_eval --limit 2000

Note: the Cardiff NLP models were trained on TweetEval's training split, so
TweetEval test scores are optimistic compared with the other two sets.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

LABELS = ["negative", "neutral", "positive"]


def load_dataset(name: str, limit: int | None) -> pd.DataFrame:
    if name == "domain":
        df = pd.read_csv(BACKEND / "eval" / "domain_labeled.csv").fillna({"aspects": ""})
    elif name == "real":
        df = pd.read_csv(BACKEND / "eval" / "real_comments_labeled.csv")
        df["aspects"] = None
    elif name == "appstore":
        import sqlite3

        from app.config import settings
        with sqlite3.connect(settings.database_path) as db:
            rows = db.execute("SELECT text, true_label FROM mentions WHERE source = 'appstore' "
                              "AND origin = 'live' AND true_label IS NOT NULL ORDER BY id").fetchall()
        df = pd.DataFrame(rows, columns=["text", "label"])
        df["aspects"] = None
    elif name == "tweet_eval":
        from huggingface_hub import hf_hub_download

        path = hf_hub_download("cardiffnlp/tweet_eval", "sentiment/test-00000-of-00001.parquet",
                               repo_type="dataset")
        df = pd.read_parquet(path)
        df = df.rename(columns={"text": "text"})
        df["label"] = df["label"].map({0: "negative", 1: "neutral", 2: "positive"})
        df["aspects"] = None
    else:
        raise ValueError(f"Unknown dataset {name}")
    if limit and len(df) > limit:
        df = df.sample(limit, random_state=42)
    return df.reset_index(drop=True)


def classification_report(y_true, y_pred) -> dict:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=LABELS, zero_division=0)
    macro = precision_recall_fscore_support(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)
    weighted = precision_recall_fscore_support(y_true, y_pred, labels=LABELS, average="weighted", zero_division=0)
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision_macro": round(float(macro[0]), 4),
        "recall_macro": round(float(macro[1]), 4),
        "f1_macro": round(float(macro[2]), 4),
        "f1_weighted": round(float(weighted[2]), 4),
        "per_class": {
            label: {"precision": round(float(p), 4), "recall": round(float(r), 4),
                    "f1": round(float(f), 4), "support": int(s)}
            for label, p, r, f, s in zip(LABELS, precision, recall, f1, support)
        },
        "confusion_matrix": {"labels": LABELS,
                             "matrix": confusion_matrix(y_true, y_pred, labels=LABELS).tolist()},
    }


def polarity_report(y_true, y_pred) -> dict:
    """Positive-vs-negative accuracy on comments that are polar and predicted polar."""
    polar = [(t, p) for t, p in zip(y_true, y_pred) if t in ("negative", "positive")]
    decisive = [(t, p) for t, p in polar if p in ("negative", "positive")]
    correct = sum(t == p for t, p in decisive)
    return {"accuracy": round(correct / len(decisive), 4) if decisive else None,
            "correct": correct, "decisive": len(decisive), "polar": len(polar),
            "coverage": round(len(decisive) / len(polar), 4) if polar else None}


def evaluate_aspects(df: pd.DataFrame, extractor) -> dict | None:
    if "aspects" not in df or df["aspects"].isna().all():
        return None
    tp = fp = fn = 0
    for text, gold in zip(df["text"], df["aspects"]):
        gold_set = {a for a in str(gold or "").split("|") if a}
        pred_set = set(extractor.find(text))
        tp += len(gold_set & pred_set)
        fp += len(pred_set - gold_set)
        fn += len(gold_set - pred_set)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def evaluate_datasets(model, datasets: list[str], output: Path, extractor=None, limit: int | None = None) -> dict:
    from app.nlp.preprocess import preprocess

    results = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    results.setdefault("datasets", {})
    for name in datasets:
        df = load_dataset(name, limit)
        texts = [preprocess(t).model_text for t in df["text"]]
        start = time.perf_counter()
        raw = model._raw_predict(texts)
        elapsed = time.perf_counter() - start
        baseline_pred = [max(p, key=p.get) for p in raw]
        hybrid_pred = [model._finalise(t, p)["label"] for t, p in zip(texts, raw)]
        entry = {
            "samples": len(df),
            "model": model.active_model,
            "inference_ms_per_text": round(1000 * elapsed / max(len(df), 1), 2),
            "hybrid": classification_report(df["label"], hybrid_pred),
            "model_only": classification_report(df["label"], baseline_pred),
            "polarity": polarity_report(df["label"], hybrid_pred),
            "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if extractor is not None:
            entry["aspect_detection"] = evaluate_aspects(df, extractor)
        errors = [{"text": t, "expected": e, "predicted": p}
                  for t, e, p in zip(df["text"], df["label"], hybrid_pred) if e != p]
        entry["sample_errors"] = errors[:15]
        results["datasets"][name] = entry
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return results


def main():
    from app.config import settings
    from app.nlp.aspects import AspectExtractor
    from app.nlp.sentiment import SentimentModel

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datasets", nargs="+", default=["domain", "real", "appstore"],
                        choices=["domain", "real", "appstore", "tweet_eval"])
    parser.add_argument("--limit", type=int, default=None, help="max samples per dataset")
    args = parser.parse_args()

    model = SentimentModel(settings.sentiment_model, settings.fallback_sentiment_model,
                           settings.model_batch_size, settings.model_max_length)
    model.load()
    results = evaluate_datasets(model, args.datasets, settings.evaluation_path, AspectExtractor(), args.limit)
    for name in args.datasets:
        r = results["datasets"][name]
        print(f"\n=== {name} ({r['samples']} samples, {r['inference_ms_per_text']} ms/text) ===")
        for variant in ("model_only", "hybrid"):
            m = r[variant]
            print(f"{variant:>16}: accuracy={m['accuracy']:.3f} precision={m['precision_macro']:.3f} "
                  f"recall={m['recall_macro']:.3f} f1={m['f1_macro']:.3f}")
        pol = r["polarity"]
        print(f"{'polarity':>16}: accuracy={pol['accuracy']:.3f} ({pol['correct']}/{pol['decisive']} "
              f"positive-vs-negative calls correct, coverage {pol['coverage']:.3f})")
        if r.get("aspect_detection"):
            a = r["aspect_detection"]
            print(f"{'aspects':>16}: precision={a['precision']:.3f} recall={a['recall']:.3f} f1={a['f1']:.3f}")
    print(f"\nSaved to {settings.evaluation_path}")


if __name__ == "__main__":
    main()
