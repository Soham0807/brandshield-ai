"""Crisis / anomaly detection.

Two complementary signals are combined to separate a real crisis from normal
fluctuation:

* Isolation Forest (multivariate, unsupervised) over per-bucket features.
* An adaptive robust z-score (median / MAD over the trailing baseline) on the
  number and share of negative mentions.

A bucket is flagged only when the anomaly points in the *harmful* direction
(more negativity), so a burst of praise is not reported as a crisis.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

FEATURES = ["total", "negative", "neg_ratio", "avg_score", "neg_delta"]
BASELINE_BUCKETS = 96  # one day of 15-minute buckets


def bucketize(df: pd.DataFrame, bucket_minutes: int, start: pd.Timestamp,
              end: pd.Timestamp) -> pd.DataFrame:
    """Aggregate mentions into fixed time buckets (empty buckets are kept)."""
    freq = f"{bucket_minutes}min"
    index = pd.date_range(start.floor(freq), end.floor(freq), freq=freq, tz="UTC")
    columns = ["total", "positive", "neutral", "negative", "spam", "avg_score", "neg_ratio"]
    if df.empty:
        out = pd.DataFrame(0.0, index=index, columns=columns)
        return out

    frame = df.copy()
    frame["bucket"] = frame["created_at"].dt.floor(freq)
    genuine = frame[~frame["is_spam"]]
    grouped = genuine.groupby("bucket")
    out = pd.DataFrame(index=index)
    out["total"] = grouped.size()
    for label in ("positive", "neutral", "negative"):
        out[label] = genuine[genuine["sentiment"] == label].groupby("bucket").size()
    out["spam"] = frame[frame["is_spam"]].groupby("bucket").size()
    out["avg_score"] = grouped["score"].mean()
    out = out.fillna(0.0)
    out["neg_ratio"] = np.where(out["total"] > 0, out["negative"] / out["total"].clip(lower=1), 0.0)
    return out[columns].astype(float)


def _robust_z(series: pd.Series, window: int) -> pd.Series:
    baseline = series.shift(1).rolling(window, min_periods=8)
    median = baseline.median()
    mad = (series.shift(1) - median).abs().rolling(window, min_periods=8).median()
    scale = (1.4826 * mad).clip(lower=0.5 if series.max() > 1 else 0.05)
    return ((series - median) / scale).fillna(0.0)


def detect_anomalies(buckets: pd.DataFrame, contamination: float = 0.05,
                     z_threshold: float = 2.5, min_negative: int = 5,
                     current_fraction: float = 1.0) -> pd.DataFrame:
    """Return buckets with anomaly columns.

    ``current_fraction`` is how much of the last (in-progress) bucket has
    elapsed; counts are extrapolated so a spike is visible before the bucket
    closes.
    """
    data = buckets.copy()
    if data.empty:
        for col in ("anomaly_score", "neg_z", "ratio_z", "is_anomaly", "if_flag"):
            data[col] = []
        return data

    if 0.2 <= current_fraction < 1.0:
        scale = 1.0 / current_fraction
        for col in ("total", "positive", "neutral", "negative", "spam"):
            data.iloc[-1, data.columns.get_loc(col)] *= scale

    data["neg_delta"] = data["negative"].diff().fillna(0.0)
    data["neg_z"] = _robust_z(data["negative"], BASELINE_BUCKETS)
    ratio = data["neg_ratio"].where(data["total"] >= 3)
    data["ratio_z"] = _robust_z(ratio.ffill().fillna(0.0), BASELINE_BUCKETS)

    data["anomaly_score"] = 0.0
    data["if_flag"] = False
    active = data[data["total"] > 0]
    if len(active) >= 24:
        model = IsolationForest(n_estimators=200, contamination=contamination, random_state=42)
        features = active[FEATURES].to_numpy(dtype=float)
        model.fit(features)
        raw = -model.score_samples(features)  # higher = more anomalous
        lo, hi = np.percentile(raw, 5), raw.max()
        normalised = np.clip((raw - lo) / max(hi - lo, 1e-9), 0, 1)
        data.loc[active.index, "anomaly_score"] = normalised
        data.loc[active.index, "if_flag"] = model.predict(features) == -1

    # The negative *share* is the primary signal: raw negative counts also rise
    # at busy hours (daily seasonality), so they only confirm the direction.
    harmful = (data["ratio_z"] >= z_threshold) & (data["neg_z"] >= z_threshold * 0.6)
    enough = data["negative"] >= min_negative
    strong_z = (data["ratio_z"] >= z_threshold * 1.6) & (data["neg_z"] >= z_threshold)
    data["is_anomaly"] = enough & ((data["if_flag"] & harmful) | strong_z)
    return data


def summarise_anomalies(data: pd.DataFrame, bucket_minutes: int) -> list[dict]:
    """Merge consecutive anomalous buckets into incidents."""
    incidents = []
    current = None
    for ts, row in data[data["is_anomaly"]].iterrows():
        if current and ts - current["_last"] <= pd.Timedelta(minutes=bucket_minutes):
            current["_last"] = ts
            current["negative"] += int(row["negative"])
            current["peak_neg_ratio"] = max(current["peak_neg_ratio"], float(row["neg_ratio"]))
            current["peak_score"] = max(current["peak_score"], float(row["anomaly_score"]))
        else:
            if current:
                incidents.append(current)
            current = {
                "start": ts,
                "_last": ts,
                "negative": int(row["negative"]),
                "peak_neg_ratio": float(row["neg_ratio"]),
                "peak_score": float(row["anomaly_score"]),
            }
    if current:
        incidents.append(current)
    for inc in incidents:
        inc["end"] = inc.pop("_last") + pd.Timedelta(minutes=bucket_minutes)
    return incidents
