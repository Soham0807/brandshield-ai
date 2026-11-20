"""Unit tests for anomaly detection and the brand-risk score."""

import numpy as np
import pandas as pd

from app.analytics.anomaly import bucketize, detect_anomalies
from app.analytics.risk import compute_risk, risk_level


def _mentions(n_hours: int, spike_last_hour: bool) -> pd.DataFrame:
    """Steady stream of mostly positive mentions, optionally with a negative spike at the end."""
    rng = np.random.default_rng(42)
    start = pd.Timestamp("2025-01-01 00:00", tz="UTC")
    rows = []
    for minute in range(0, n_hours * 60, 3):
        rows.append({"created_at": start + pd.Timedelta(minutes=minute),
                     "sentiment": rng.choice(["positive", "neutral", "negative"], p=[0.6, 0.3, 0.1])})
    if spike_last_hour:
        spike_start = start + pd.Timedelta(hours=n_hours - 1)
        for i in range(120):
            rows.append({"created_at": spike_start + pd.Timedelta(seconds=30 * i), "sentiment": "negative"})
    df = pd.DataFrame(rows)
    df["score"] = df["sentiment"].map({"positive": 0.8, "neutral": 0.0, "negative": -0.8})
    df["is_spam"] = False
    return df.sort_values("created_at").reset_index(drop=True)


def _analyse(df):
    buckets = bucketize(df, 15, df["created_at"].min(), df["created_at"].max())
    return detect_anomalies(buckets)


def test_risk_levels_follow_thresholds():
    assert risk_level(0) == "low"
    assert risk_level(30) == "medium"
    assert risk_level(55) == "high"
    assert risk_level(90) == "critical"


def test_bucketize_keeps_empty_buckets():
    empty = pd.DataFrame(columns=["created_at", "sentiment", "score", "is_spam"])
    start = pd.Timestamp("2025-01-01 00:00", tz="UTC")
    out = bucketize(empty, 15, start, start + pd.Timedelta(hours=1))
    assert len(out) == 5
    assert out["total"].sum() == 0


def test_bucketize_counts_every_mention():
    df = _mentions(6, spike_last_hour=False)
    buckets = bucketize(df, 15, df["created_at"].min(), df["created_at"].max())
    assert int(buckets["total"].sum()) == len(df)


def test_negative_spike_is_flagged_as_anomaly():
    data = _analyse(_mentions(24, spike_last_hour=True))
    assert data["is_anomaly"].tail(4).any()


def test_calm_stream_has_no_recent_anomaly():
    data = _analyse(_mentions(24, spike_last_hour=False))
    assert not data["is_anomaly"].tail(4).any()


def test_spike_raises_risk_above_calm_stream():
    calm = compute_risk(_analyse(_mentions(24, False)), 15, None, [], min_negative=5)
    crisis = compute_risk(_analyse(_mentions(24, True)), 15, None, [], min_negative=5)
    assert crisis["score"] > calm["score"]
    assert crisis["level"] in ("high", "critical")
    assert crisis["drivers"], "a crisis should explain what drove the score"


def test_empty_data_gives_zero_risk():
    assert compute_risk(pd.DataFrame(), 15, None, [], min_negative=5)["score"] == 0
