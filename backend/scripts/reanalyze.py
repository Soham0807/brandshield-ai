"""Re-run sentiment and topic analysis on stored mentions with the current model.

Use after changing the sentiment model or the topic list, with the server STOPPED
(it writes to the database directly).

Usage (from the backend folder):
    python -m scripts.reanalyze              # every mention
    python -m scripts.reanalyze --days 30    # only the last 30 days
    python -m scripts.reanalyze --before 2026-09-30T00:23:28Z   # resume a run that was cut off
"""

import argparse
import json
import sys
import time
from datetime import timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def main():
    from app.config import settings
    from app.db import Database, to_iso, utcnow
    from app.nlp.aspects import AspectExtractor
    from app.nlp.preprocess import preprocess
    from app.nlp.sentiment import SentimentModel
    from app.runtime import RuntimeConfig

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=float, default=None, help="only mentions from the last N days")
    parser.add_argument("--before", default=None, help="only mentions created before this UTC time (resume a cut-off run)")
    parser.add_argument("--batch", type=int, default=64)
    args = parser.parse_args()

    db = Database(settings.database_path)
    aspects = AspectExtractor(RuntimeConfig(db, settings).get()["aspects"])
    model = SentimentModel(settings.sentiment_model, settings.fallback_sentiment_model,
                           settings.model_batch_size, settings.model_max_length)
    model.load()
    print(f"Model: {model.active_model}", flush=True)

    conds, params = [], []
    if args.days:
        conds.append("created_at >= ?")
        params.append(to_iso(utcnow() - timedelta(days=args.days)))
    if args.before:
        conds.append("created_at < ?")
        params.append(args.before)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    rows = db.query(f"SELECT id, text FROM mentions {where} ORDER BY created_at DESC", params)
    print(f"Re-analysing {len(rows)} mentions", flush=True)
    changed, start = 0, time.time()
    for i in range(0, len(rows), args.batch):
        chunk = rows[i:i + args.batch]
        texts = [preprocess(r["text"]).model_text for r in chunk]
        sentiments = model.predict(texts)
        topic_lists = aspects.analyze_batch(texts, sentiments, model)
        old = {r["id"]: r["sentiment"] for r in db.query(
            f"SELECT id, sentiment FROM mentions WHERE id IN ({','.join('?' * len(chunk))})", [r["id"] for r in chunk])}
        updates = [(s["label"], s["confidence"], s["score"], json.dumps(s["probs"]), json.dumps(t), r["id"])
                   for r, s, t in zip(chunk, sentiments, topic_lists)]
        changed += sum(1 for r, s in zip(chunk, sentiments) if old.get(r["id"]) != s["label"])
        with db._lock:
            db._conn.executemany(
                "UPDATE mentions SET sentiment=?, confidence=?, score=?, probs=?, aspects=? WHERE id=?", updates)
            db._conn.commit()
        done = min(i + args.batch, len(rows))
        if (i // args.batch) % 10 == 0 or done == len(rows):
            rate = done / max(time.time() - start, 1e-6)
            print(f"  {done}/{len(rows)}  ({rate:.1f}/s, {changed} labels changed)", flush=True)
    db.close()
    print(f"Done: {len(rows)} mentions, {changed} changed sentiment, {time.time() - start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
