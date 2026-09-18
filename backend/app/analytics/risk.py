"""Brand risk score (0-100) that combines sentiment, velocity, anomaly,
forecast and aspect-concentration signals to reduce false crisis alerts."""

import pandas as pd

LEVELS = [(75, "critical"), (55, "high"), (30, "medium"), (0, "low")]


def risk_level(score: float) -> str:
    for threshold, name in LEVELS:
        if score >= threshold:
            return name
    return "low"


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def compute_risk(anomalies: pd.DataFrame, bucket_minutes: int, forecast_score: dict | None,
                 recent_aspects: list[dict], min_negative: int) -> dict:
    recent_n = max(1, 60 // bucket_minutes)
    if anomalies.empty:
        return {"score": 0, "level": "low", "components": {}, "drivers": []}

    recent = anomalies.tail(recent_n)
    baseline = anomalies.iloc[:-recent_n].tail(96)
    recent_total = float(recent["total"].sum())
    recent_negative = float(recent["negative"].sum())
    recent_ratio = recent_negative / recent_total if recent_total else 0.0
    base_total = float(baseline["total"].sum())
    base_ratio = float(baseline["negative"].sum()) / base_total if base_total else 0.0

    drivers = []

    # 1. Negativity level + lift over baseline (0-35)
    lift = recent_ratio - base_ratio
    sentiment_pts = 35 * _clamp(0.55 * recent_ratio / 0.5 + 0.45 * _clamp(lift / 0.3))
    if recent_total >= 3 and lift > 0.08:
        drivers.append(f"Negative share is {recent_ratio:.0%} in the last hour vs {base_ratio:.0%} baseline")

    # 2. Velocity of negative mentions (0-20)
    max_z = float(recent["neg_z"].max()) if "neg_z" in recent else 0.0
    velocity_pts = 20 * _clamp(max_z / 6)
    if max_z >= 3 and recent_negative >= min_negative:
        drivers.append(f"Negative mentions are rising fast (z-score {max_z:.1f})")

    # 3. Anomaly detector (0-25)
    anomaly_pts = 0.0
    if recent["is_anomaly"].any():
        anomaly_pts = 25 * _clamp(0.5 + 0.5 * float(recent["anomaly_score"].max()))
        drivers.append("Isolation Forest flagged an abnormal negative spike")

    # 4. Forecast (0-10)
    forecast_pts = 0.0
    points = (forecast_score or {}).get("points") or []
    if points:
        current = float(anomalies["avg_score"].tail(recent_n * 3).mean())
        future = min(p["yhat"] for p in points[:6])
        drop = current - future
        forecast_pts = 10 * _clamp(drop / 0.4)
        if drop > 0.15:
            drivers.append(f"Sentiment forecast declines by {drop:.2f} over the next hours")

    # 5. Concentration on one aspect (0-10)
    concentration_pts = 0.0
    negatives = [a for a in recent_aspects if a["negative"] > 0]
    total_aspect_neg = sum(a["negative"] for a in negatives)
    if total_aspect_neg >= min_negative:
        top = max(negatives, key=lambda a: a["negative"])
        share = top["negative"] / total_aspect_neg
        concentration_pts = 10 * _clamp((share - 0.3) / 0.5)
        if share >= 0.5:
            drivers.append(f"{share:.0%} of complaints are about {top['aspect'].replace('_', ' ')}")

    components = {
        "negativity": round(sentiment_pts, 1),
        "velocity": round(velocity_pts, 1),
        "anomaly": round(anomaly_pts, 1),
        "forecast": round(forecast_pts, 1),
        "concentration": round(concentration_pts, 1),
    }
    score = round(min(100.0, sum(components.values())))
    return {
        "score": score,
        "level": risk_level(score),
        "components": components,
        "drivers": drivers,
        "recent_negative_ratio": round(recent_ratio, 4),
        "baseline_negative_ratio": round(base_ratio, 4),
    }
