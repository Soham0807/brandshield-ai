"""Alert rules evaluated after every analytics snapshot.

Alerts combine several signals (risk score, anomaly detector, aspect surge,
forecast, spam volume, viral negative posts) and use a cool-down per rule so
the team is not flooded with duplicates.
"""

import json
from datetime import timedelta

from app.db import Database, from_iso, to_iso, utcnow


class AlertEngine:
    def __init__(self, db: Database, runtime, notifier, hub):
        self.db = db
        self.runtime = runtime
        self.notifier = notifier
        self.hub = hub

    # ------------------------------------------------------------------
    def _recently_fired(self, dedupe_key: str, cooldown_minutes: int) -> bool:
        since = to_iso(utcnow() - timedelta(minutes=cooldown_minutes))
        return bool(self.db.scalar(
            "SELECT 1 FROM alerts WHERE dedupe_key = ? AND created_at >= ? LIMIT 1", (dedupe_key, since)))

    async def raise_alert(self, severity: str, type_: str, title: str, message: str, meta: dict,
                          dedupe_key: str | None = None, cooldown: int | None = None) -> dict | None:
        cfg = self.runtime.get()
        cooldown = cooldown if cooldown is not None else int(cfg["thresholds"]["alert_cooldown_minutes"])
        key = dedupe_key or type_
        if cooldown and self._recently_fired(key, cooldown):
            return None
        now = to_iso(utcnow())
        alert_id = self.db.execute(
            "INSERT INTO alerts(created_at, severity, type, dedupe_key, title, message, meta, status, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)",
            (now, severity, type_, key, title, message, json.dumps(meta), now),
        )
        alert = {"id": alert_id, "created_at": now, "severity": severity, "type": type_, "title": title,
                 "message": message, "meta": meta, "status": "open"}
        delivery = await self.notifier.send(alert, cfg["notifications"], cfg["brand_name"])
        if delivery:
            alert["meta"]["delivery"] = delivery
            self.db.execute("UPDATE alerts SET meta = ? WHERE id = ?", (json.dumps(alert["meta"]), alert_id))
        await self.hub.broadcast("alert", alert)
        return alert

    # ------------------------------------------------------------------
    async def evaluate(self, snapshot: dict, forecast: dict) -> list[dict]:
        cfg = self.runtime.get()
        t = cfg["thresholds"]
        min_neg = int(t["min_negative_mentions"])
        raised = []

        risk = snapshot["risk"]
        recent = snapshot["recent"]
        anomalies = snapshot.get("_anomalies")

        # 1) anomaly detector flagged the current hour
        if anomalies is not None and not anomalies.empty:
            window = anomalies.tail(max(1, 60 // 15))
            if window["is_anomaly"].any():
                peak = window[window["is_anomaly"]].iloc[-1]
                severity = "critical" if risk["score"] >= 75 else "high"
                a = await self.raise_alert(
                    severity, "negative_spike", "Sudden spike in negative sentiment",
                    f"Negative mentions jumped to {peak['neg_ratio']:.0%} of conversation "
                    f"(robust z-score {peak['neg_z']:.1f}). Isolation Forest anomaly score "
                    f"{peak['anomaly_score']:.2f}. " + "".join(f"{d}. " for d in risk.get("drivers", [])[:2]).strip(),
                    {"risk": risk["score"], "neg_ratio": float(peak["neg_ratio"]),
                     "anomaly_score": float(peak["anomaly_score"])},
                    dedupe_key="negative_spike",
                )
                raised.append(a)

        # 2) overall risk above the configured threshold
        if risk["score"] >= float(t["risk_alert"]):
            a = await self.raise_alert(
                "critical" if risk["score"] >= 75 else "high", "risk_threshold",
                f"Brand risk score reached {risk['score']}/100",
                "Risk drivers: " + ("; ".join(risk.get("drivers", [])) or "combined negative signals") + ".",
                {"risk": risk},
                dedupe_key="risk_threshold",
            )
            raised.append(a)

        # 3) negative share above threshold with enough volume
        if recent["total"] >= 10 and recent["negative"] >= min_neg and \
                recent["negative_pct"] / 100 >= float(t["negative_ratio_alert"]):
            a = await self.raise_alert(
                "medium", "negative_ratio", "Negative sentiment increased",
                f"{recent['negative_pct']:.0f}% of the {recent['total']} mentions in the last hour are negative "
                f"(threshold {float(t['negative_ratio_alert']):.0%}).",
                {"recent": recent},
                dedupe_key="negative_ratio",
            )
            raised.append(a)

        # 4) complaints concentrated on one aspect
        for aspect in snapshot.get("recent_aspects", []):
            if aspect["negative"] >= max(min_neg, 3) and aspect["negative_pct"] >= 50:
                name = aspect["aspect"].replace("_", " ")
                a = await self.raise_alert(
                    "high" if aspect["negative"] >= min_neg * 2 else "medium", "aspect_surge",
                    f"Multiple {name} complaints detected",
                    f"{aspect['negative']} of {aspect['total']} mentions about {name} in the last hour are negative.",
                    {"aspect": aspect["aspect"], "stats": aspect},
                    dedupe_key=f"aspect_surge:{aspect['aspect']}",
                )
                raised.append(a)

        # 5) forecast predicts declining sentiment
        points = ((forecast or {}).get("sentiment") or {}).get("points") or []
        if points:
            worst = min(points[:6], key=lambda p: p["yhat"])
            if worst["yhat"] < float(t["forecast_score_floor"]):
                a = await self.raise_alert(
                    "medium", "forecast_decline", "Sentiment expected to decline",
                    f"Prophet forecasts the sentiment index to fall to {worst['yhat']:.2f} "
                    f"by {worst['t']} (floor {float(t['forecast_score_floor']):.2f}).",
                    {"forecast_point": worst},
                    dedupe_key="forecast_decline", cooldown=120,
                )
                raised.append(a)

        # 6) spam wave
        if recent["spam"] >= int(t["spam_wave"]):
            a = await self.raise_alert(
                "low", "spam_wave", f"{recent['spam']} spam comments detected",
                f"AI detected and flagged {recent['spam']} spam or bot comments in the last hour. "
                "They are excluded from sentiment metrics.",
                {"spam": recent["spam"]},
                dedupe_key="spam_wave", cooldown=60,
            )
            raised.append(a)
        return [a for a in raised if a]

    async def check_mentions(self, mentions: list[dict]) -> None:
        """Per-mention rule: a negative post with very high engagement."""
        threshold = int(self.runtime.get()["thresholds"]["viral_engagement"])
        for m in mentions:
            if m["sentiment"] == "negative" and not m["is_spam"] and m.get("engagement", 0) >= threshold:
                await self.raise_alert(
                    "high", "viral_negative", "Negative post is going viral",
                    f"A negative {m['source']} post by @{m.get('author') or 'unknown'} has "
                    f"{m['engagement']} interactions: \"{m['text'][:180]}\"",
                    {"mention_id": m["id"], "engagement": m["engagement"], "source": m["source"]},
                    dedupe_key=f"viral_negative:{m['id']}", cooldown=0,
                )

    # ------------------------------------------------------------------
    def list(self, status: str | None = None, limit: int = 100) -> list[dict]:
        if status:
            rows = self.db.query("SELECT * FROM alerts WHERE status = ? ORDER BY id DESC LIMIT ?", (status, limit))
        else:
            rows = self.db.query("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,))
        for r in rows:
            r["meta"] = json.loads(r["meta"]) if r.get("meta") else {}
        return rows

    def set_status(self, alert_id: int, status: str) -> bool:
        exists = self.db.scalar("SELECT 1 FROM alerts WHERE id = ?", (alert_id,))
        if not exists:
            return False
        self.db.execute("UPDATE alerts SET status = ?, updated_at = ? WHERE id = ?",
                        (status, to_iso(utcnow()), alert_id))
        return True

    def age_minutes(self, created_at: str) -> float:
        return (utcnow() - from_iso(created_at)).total_seconds() / 60
