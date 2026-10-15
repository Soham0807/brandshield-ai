"""Aggregations served to the dashboard + the periodic analytics snapshot
(anomalies, risk, forecast) used by the alert engine."""

import json
import threading
import time
from collections import Counter
from datetime import timedelta

import numpy as np
import pandas as pd

from app.analytics import anomaly as anomaly_mod
from app.analytics.forecast import forecast
from app.analytics.risk import compute_risk, recent_bucket_count
from app.config import Settings
from app.db import Database, to_iso, utcnow
from app.runtime import RuntimeConfig

GENERIC_WORDS = {"cafe", "place", "order", "today", "time", "go", "went", "come", "came",
                 "make", "made", "one", "also", "would", "could", "back", "day", "really",
                 "saffron", "brand", "like", "u", "amp", "get", "got"}


class AnalyticsService:
    def __init__(self, db: Database, runtime: RuntimeConfig, settings: Settings):
        self.db = db
        self.runtime = runtime
        self.settings = settings
        self._cache: dict = {}
        self._cache_lock = threading.Lock()
        self.latest: dict = {"risk": {"score": 0, "level": "low", "components": {}, "drivers": []},
                             "incidents": [], "computed_at": None}
        self.forecast_data: dict = {"computed_at": None}
        self._forecast_lock = threading.Lock()

    # ------------------------------------------------------------------
    # loading
    # ------------------------------------------------------------------
    def load(self, hours: float, until=None) -> pd.DataFrame:
        key = ("load", round(hours, 3), until)
        with self._cache_lock:
            hit = self._cache.get(key)
            if hit and hit[0] > time.monotonic():
                return hit[1]
        end = until or utcnow()
        since = to_iso(end - timedelta(hours=hours))
        rows = self.db.query(
            "SELECT id, source, created_at, sentiment, score, is_spam, aspects, keywords, "
            "language, engagement FROM mentions WHERE created_at >= ? AND created_at <= ?",
            (since, to_iso(end)),
        )
        df = pd.DataFrame(rows, columns=["id", "source", "created_at", "sentiment", "score", "is_spam",
                                         "aspects", "keywords", "language", "engagement"])
        if not df.empty:
            df["created_at"] = pd.to_datetime(df["created_at"], utc=True, format="%Y-%m-%dT%H:%M:%SZ")
            df["is_spam"] = df["is_spam"].astype(bool)
            df["score"] = df["score"].astype(float)
        else:
            df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
            df["is_spam"] = df["is_spam"].astype(bool)
        with self._cache_lock:
            self._cache[key] = (time.monotonic() + 3.0, df)
            if len(self._cache) > 64:
                self._cache.clear()
        return df

    # ------------------------------------------------------------------
    # building blocks
    # ------------------------------------------------------------------
    @staticmethod
    def sentiment_counts(df: pd.DataFrame) -> dict:
        genuine = df[~df["is_spam"]] if not df.empty else df
        total = int(len(genuine))
        counts = {label: int((genuine["sentiment"] == label).sum()) if total else 0
                  for label in ("positive", "neutral", "negative")}
        pct = {f"{k}_pct": round(100 * v / total, 1) if total else 0.0 for k, v in counts.items()}
        avg = float(genuine["score"].mean()) if total else 0.0
        return {
            "total": total,
            **counts,
            **pct,
            "spam": int(df["is_spam"].sum()) if not df.empty else 0,
            "avg_score": round(avg, 4),
            "health": int(round(max(0.0, min(100.0, 50 + 50 * avg)))) if total else None,
        }

    @staticmethod
    def aspect_table(df: pd.DataFrame) -> list[dict]:
        stats: dict[str, dict] = {}
        genuine = df[~df["is_spam"]] if not df.empty else df
        for raw in genuine["aspects"].dropna() if not genuine.empty else []:
            for item in json.loads(raw):
                s = stats.setdefault(item["aspect"], {"aspect": item["aspect"], "total": 0, "positive": 0,
                                                      "neutral": 0, "negative": 0, "_score": 0.0})
                s["total"] += 1
                s[item["sentiment"]] += 1
                s["_score"] += item["score"]
        table = []
        for s in stats.values():
            s["avg_score"] = round(s.pop("_score") / s["total"], 4)
            s["negative_pct"] = round(100 * s["negative"] / s["total"], 1)
            table.append(s)
        return sorted(table, key=lambda s: s["total"], reverse=True)

    def top_keywords(self, df: pd.DataFrame, sentiment: str, limit: int = 12) -> list[dict]:
        if df.empty:
            return []
        subset = df[(~df["is_spam"]) & (df["sentiment"] == sentiment)]
        brand_words = {w.lower() for k in self.runtime.get()["keywords"] + [self.runtime.get()["brand_name"]]
                       for w in k.replace("_", " ").split()}
        counter: Counter = Counter()
        for kw in subset["keywords"].dropna():
            words = [w for w in kw.split() if w not in GENERIC_WORDS and w not in brand_words and len(w) > 2]
            counter.update(set(words))
        return [{"word": w, "count": c} for w, c in counter.most_common(limit)]

    # ------------------------------------------------------------------
    # dashboard endpoints
    # ------------------------------------------------------------------
    def trends(self, hours: float, bucket_minutes: int | None = None) -> dict:
        bucket = bucket_minutes or self._auto_bucket(hours)
        now = utcnow()
        df = self.load(hours)
        start = pd.Timestamp(now - timedelta(hours=hours))
        buckets = anomaly_mod.bucketize(df, bucket, start, pd.Timestamp(now))
        flags = self._anomaly_flags()
        points = []
        for ts, row in buckets.iterrows():
            points.append({
                "t": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "total": int(row["total"]),
                "positive": int(row["positive"]),
                "neutral": int(row["neutral"]),
                "negative": int(row["negative"]),
                "spam": int(row["spam"]),
                "avg_score": round(float(row["avg_score"]), 4),
                "neg_ratio": round(float(row["neg_ratio"]), 4),
                "anomaly": any(ts <= f < ts + pd.Timedelta(minutes=bucket) for f in flags),
            })
        return {"bucket_minutes": bucket, "points": points}

    @staticmethod
    def _auto_bucket(hours: float) -> int:
        if hours <= 6:
            return 15
        if hours <= 48:
            return 60
        return 180

    def _anomaly_flags(self) -> list[pd.Timestamp]:
        data = self.latest.get("_anomalies")
        if data is None or data.empty:
            return []
        return list(data.index[data["is_anomaly"]])

    def overview(self, hours: float) -> dict:
        now = utcnow()
        both = self.load(hours * 2)
        cutoff = pd.Timestamp(now - timedelta(hours=hours))
        current = both[both["created_at"] >= cutoff] if not both.empty else both
        previous = both[both["created_at"] < cutoff] if not both.empty else both
        cur, prev = self.sentiment_counts(current), self.sentiment_counts(previous)

        def delta(key):
            a, b = cur.get(key), prev.get(key)
            if a is None or b is None:
                return None
            return round(a - b, 2)

        def pct_change(key):
            a, b = cur.get(key) or 0, prev.get(key) or 0
            return round(100 * (a - b) / b, 1) if b else None

        sources = current["source"].value_counts().to_dict() if not current.empty else {}
        genuine = current[~current["is_spam"]] if not current.empty else current
        languages = genuine["language"].value_counts().head(8).to_dict() if not genuine.empty else {}
        aspects_now = self.aspect_table(current)
        aspects_prev = {a["aspect"]: a for a in self.aspect_table(previous)}
        for a in aspects_now:
            before = aspects_prev.get(a["aspect"], {}).get("negative", 0)
            a["negative_change_pct"] = round(100 * (a["negative"] - before) / before, 1) if before else None

        open_alerts = self.db.query(
            "SELECT severity, COUNT(*) AS n FROM alerts WHERE status = 'open' GROUP BY severity")
        risk = self.latest.get("risk", {})
        summary = self.build_summary(hours, cur, prev, aspects_now, risk, current)
        return {
            "window_hours": hours,
            "brand_name": self.runtime.get()["brand_name"],
            "generated_at": to_iso(now),
            "current": cur,
            "previous": prev,
            "deltas": {
                "total_pct": pct_change("total"),
                "positive_pct": delta("positive_pct"),
                "negative_pct": delta("negative_pct"),
                "health": delta("health"),
                "spam_pct": pct_change("spam"),
            },
            "sources": sources,
            "languages": languages,
            "aspects": aspects_now,
            "risk": risk,
            "open_alerts": {r["severity"]: r["n"] for r in open_alerts},
            "summary": summary,
            "negative_keywords": self.top_keywords(current, "negative", 10),
            "positive_keywords": self.top_keywords(current, "positive", 10),
        }

    def build_summary(self, hours, cur, prev, aspects, risk, current_df) -> str:
        if not cur["total"]:
            return "No mentions have been collected in this period yet. Add a YouTube channel or connect an Instagram account to start."
        window = f"the last {int(hours)} hours" if hours != 24 else "the last 24 hours"
        mood = ("mostly positive" if cur["positive_pct"] >= 55 else
                "mostly negative" if cur["negative_pct"] >= 45 else "mixed")
        parts = [f"Your audience is {mood} ({cur['positive_pct']:.0f}% positive, "
                 f"{cur['negative_pct']:.0f}% negative) across {cur['total']} mentions in {window}."]
        worst = sorted((a for a in aspects if a["negative"] >= 3), key=lambda a: a["negative"], reverse=True)
        if worst:
            a = worst[0]
            change = a.get("negative_change_pct")
            trend = (f", up {change:.0f}% from the previous period" if change and change > 10 else
                     f", down {abs(change):.0f}% from the previous period" if change and change < -10 else "")
            parts.append(f"The biggest source of complaints is {a['aspect'].replace('_', ' ')} "
                         f"with {a['negative']} negative mentions{trend}.")
        best = sorted((a for a in aspects if a["positive"] >= 3), key=lambda a: a["avg_score"], reverse=True)
        if best:
            parts.append(f"Customers are happiest with {best[0]['aspect'].replace('_', ' ')}.")
        if cur["spam"]:
            parts.append(f"{cur['spam']} spam mentions were detected and excluded from the analysis.")
        level = risk.get("level", "low")
        if level in ("high", "critical"):
            parts.append(f"Brand risk is {level.upper()} ({risk.get('score')}/100) - "
                         + "; ".join(risk.get("drivers", [])[:2]) + ".")
        else:
            parts.append(f"Brand risk is {level} ({risk.get('score', 0)}/100).")
        fc = (self.forecast_data.get("sentiment") or {}).get("points") or []
        if fc:
            direction = fc[-1]["yhat"] - fc[0]["yhat"]
            if abs(direction) < 0.05:
                parts.append("Sentiment is forecast to remain stable over the next hours.")
            else:
                parts.append(f"Sentiment is forecast to {'improve' if direction > 0 else 'decline'} "
                             f"over the next {len(fc)} hours.")
        return " ".join(parts)

    def aspects(self, hours: float) -> dict:
        now = utcnow()
        both = self.load(hours * 2)
        cutoff = pd.Timestamp(now - timedelta(hours=hours))
        current = both[both["created_at"] >= cutoff] if not both.empty else both
        previous = both[both["created_at"] < cutoff] if not both.empty else both
        table = self.aspect_table(current)
        prev = {a["aspect"]: a for a in self.aspect_table(previous)}
        for a in table:
            p = prev.get(a["aspect"])
            a["previous_negative"] = p["negative"] if p else 0
            a["previous_avg_score"] = p["avg_score"] if p else None
        configured = list(self.runtime.get()["aspects"].keys())
        return {
            "window_hours": hours,
            "aspects": table,
            "configured": configured,
            "negative_keywords": self.top_keywords(current, "negative", 15),
            "positive_keywords": self.top_keywords(current, "positive", 15),
        }

    # ------------------------------------------------------------------
    # periodic analytics (runs in a worker thread)
    # ------------------------------------------------------------------
    def compute_snapshot(self) -> dict:
        cfg = self.runtime.get()
        t = cfg["thresholds"]
        bucket = self.settings.bucket_minutes
        now = utcnow()
        df = self.load(72)
        start = pd.Timestamp(now - timedelta(hours=72))
        buckets = anomaly_mod.bucketize(df, bucket, start, pd.Timestamp(now))
        elapsed = (pd.Timestamp(now) - buckets.index[-1]).total_seconds() / (bucket * 60) if len(buckets) else 1
        anomalies = anomaly_mod.detect_anomalies(
            buckets,
            contamination=float(t["anomaly_contamination"]),
            z_threshold=float(t["z_threshold"]),
            min_negative=int(t["min_negative_mentions"]),
            current_fraction=min(1.0, max(elapsed, 0.01)),
        )
        recent_df = df[df["created_at"] >= pd.Timestamp(now - timedelta(hours=1))] if not df.empty else df
        recent_aspects = self.aspect_table(recent_df)
        # the risk score widens its "recent" window on low-volume sources (see risk.recent_bucket_count);
        # alert rules keep using the one-hour window above
        risk_n = recent_bucket_count(anomalies, bucket)
        risk_hours = risk_n * bucket / 60
        if risk_hours > 1 and not df.empty:
            risk_df = df[df["created_at"] >= pd.Timestamp(now - timedelta(hours=risk_hours))]
            risk_aspects = self.aspect_table(risk_df)
        else:
            risk_aspects = recent_aspects
        risk = compute_risk(anomalies, bucket, self.forecast_data.get("sentiment"), risk_aspects,
                            int(t["min_negative_mentions"]), recent_n=risk_n)
        incidents = anomaly_mod.summarise_anomalies(anomalies, bucket)
        recent_counts = self.sentiment_counts(recent_df)
        # risk history for the chart (score per hour, simplified)
        snapshot = {
            "computed_at": to_iso(now),
            "risk": risk,
            "incidents": [
                {"start": i["start"].strftime("%Y-%m-%dT%H:%M:%SZ"), "end": i["end"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "negative": i["negative"], "peak_neg_ratio": round(i["peak_neg_ratio"], 3),
                 "peak_score": round(i["peak_score"], 3)}
                for i in incidents
            ],
            "recent": recent_counts,
            "recent_aspects": recent_aspects,
            "_anomalies": anomalies,
        }
        self.latest = snapshot
        return snapshot

    def anomalies(self, hours: float) -> dict:
        data = self.latest.get("_anomalies")
        if data is None:
            return {"bucket_minutes": self.settings.bucket_minutes, "points": [], "incidents": []}
        cutoff = pd.Timestamp(utcnow() - timedelta(hours=hours))
        window = data[data.index >= cutoff]
        points = [{
            "t": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total": round(float(r["total"]), 1),
            "negative": round(float(r["negative"]), 1),
            "neg_ratio": round(float(r["neg_ratio"]), 4),
            "avg_score": round(float(r["avg_score"]), 4),
            "anomaly_score": round(float(r["anomaly_score"]), 4),
            "neg_z": round(float(r["neg_z"]), 2),
            "ratio_z": round(float(r["ratio_z"]), 2),
            "is_anomaly": bool(r["is_anomaly"]),
        } for ts, r in window.iterrows()]
        incidents = [i for i in self.latest["incidents"] if i["end"] >= cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")]
        return {"bucket_minutes": self.settings.bucket_minutes, "points": points, "incidents": incidents,
                "computed_at": self.latest["computed_at"]}

    def refresh_forecast(self) -> dict:
        with self._forecast_lock:
            now = utcnow()
            horizon = self.settings.forecast_horizon_hours
            df = self.load(24 * 7)
            if df.empty:
                self.forecast_data = {"computed_at": to_iso(now), "history": [], "sentiment": None,
                                      "negative_ratio": None, "volume": None}
                return self.forecast_data
            first = df["created_at"].min()
            hourly = anomaly_mod.bucketize(df, 60, first, pd.Timestamp(now))
            complete = hourly.iloc[:-1] if len(hourly) > 1 else hourly  # drop in-progress hour
            complete = complete.loc[complete["total"].cumsum() > 0]
            score = complete["avg_score"].where(complete["total"] > 0).interpolate().bfill()
            ratio = complete["neg_ratio"].where(complete["total"] > 0).interpolate().bfill()
            result = {
                "computed_at": to_iso(now),
                "horizon_hours": horizon,
                "history": [{"t": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "avg_score": round(float(s), 4),
                             "neg_ratio": round(float(r), 4), "volume": int(v)}
                            for ts, s, r, v in zip(complete.index, score, ratio, complete["total"])][-72:],
                "sentiment": forecast(score, horizon, -1.0, 1.0),
                "negative_ratio": forecast(ratio, horizon, 0.0, 1.0),
                "volume": forecast(complete["total"].astype(float), horizon, 0.0, None),
            }
            self.forecast_data = result
            return result

    def public_forecast(self) -> dict:
        return self.forecast_data


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    raise TypeError
