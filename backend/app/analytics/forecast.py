"""Sentiment forecasting with Prophet (Holt linear smoothing as a fallback
when there is too little history or Prophet is unavailable)."""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger("brandshield.forecast")
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet").setLevel(logging.WARNING)

try:
    from prophet import Prophet
except Exception:  # pragma: no cover
    Prophet = None

MIN_PROPHET_POINTS = 36  # hours


def _holt(series: pd.Series, horizon: int, alpha: float = 0.5, beta: float = 0.2):
    values = series.to_numpy(dtype=float)
    level, trend = values[0], (values[1] - values[0]) if len(values) > 1 else 0.0
    residuals = []
    for v in values[1:]:
        prev = level + trend
        residuals.append(v - prev)
        new_level = alpha * v + (1 - alpha) * prev
        trend = beta * (new_level - level) + (1 - beta) * trend
        level = new_level
    sigma = float(np.std(residuals)) if residuals else 0.0
    steps = np.arange(1, horizon + 1)
    yhat = level + trend * steps
    spread = 1.28 * sigma * np.sqrt(steps)
    return yhat, yhat - spread, yhat + spread


def forecast(series: pd.Series, horizon: int, lower: float | None = None,
             upper: float | None = None) -> dict:
    """Forecast an hourly series. ``series`` is indexed by UTC timestamps."""
    series = series.dropna()
    if len(series) < 6:
        return {"method": "insufficient_data", "points": []}

    last = series.index[-1]
    future_index = pd.date_range(last + pd.Timedelta(hours=1), periods=horizon, freq="h")
    method = "holt"
    try:
        if Prophet is None or len(series) < MIN_PROPHET_POINTS:
            raise RuntimeError("using Holt fallback")
        frame = pd.DataFrame({"ds": series.index.tz_convert(None), "y": series.values})
        model = Prophet(
            daily_seasonality=len(series) >= 48,
            weekly_seasonality=len(series) >= 24 * 14,
            yearly_seasonality=False,
            interval_width=0.8,
            changepoint_prior_scale=0.08,
        )
        model.fit(frame)
        future = pd.DataFrame({"ds": future_index.tz_convert(None)})
        pred = model.predict(future)
        yhat, ylo, yhi = pred["yhat"].to_numpy(), pred["yhat_lower"].to_numpy(), pred["yhat_upper"].to_numpy()
        method = "prophet"
    except Exception as exc:
        if Prophet is not None and len(series) >= MIN_PROPHET_POINTS:
            logger.warning("Prophet failed (%s); falling back to Holt smoothing", exc)
        yhat, ylo, yhi = _holt(series, horizon)

    def clip(arr):
        return np.clip(arr, lower if lower is not None else -np.inf, upper if upper is not None else np.inf)

    yhat, ylo, yhi = clip(yhat), clip(ylo), clip(yhi)
    points = [
        {"t": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "yhat": round(float(a), 4),
         "lower": round(float(b), 4), "upper": round(float(c), 4)}
        for ts, a, b, c in zip(future_index, yhat, ylo, yhi)
    ]
    return {"method": method, "points": points}
