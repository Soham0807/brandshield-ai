"""User-editable configuration persisted in the database.

Changed from the Settings page of the dashboard; every component reads the
current values through ``RuntimeConfig.get()`` so changes apply immediately.
"""

import copy
import threading

from app.config import Settings
from app.db import Database
from app.nlp.aspects import DEFAULT_ASPECTS

SEVERITIES = ["low", "medium", "high", "critical"]


def build_defaults(settings: Settings) -> dict:
    return {
        "brand_name": settings.brand_name,
        "keywords": settings.keyword_list,
        "sources": {
            "simulator": settings.enable_simulator,
            "reddit": settings.enable_reddit,
            "rss": settings.enable_rss,
            "twitter": settings.enable_twitter,
            "youtube": settings.enable_youtube,
            "appstore": settings.enable_appstore,
            "instagram": False,  # switched on automatically when an account is connected
            "instagram_pages": False,  # switched on automatically when a public page is added
        },
        "simulator_rate_per_min": settings.simulator_rate_per_min,
        "aspects": copy.deepcopy(DEFAULT_ASPECTS),
        "thresholds": {
            # overall risk score (0-100) that raises an alert
            "risk_alert": 60,
            # share of negative mentions in the last hour that raises an alert
            "negative_ratio_alert": 0.35,
            # minimum number of negatives before any spike alert fires
            "min_negative_mentions": 5,
            # Isolation Forest expected outlier share
            "anomaly_contamination": 0.05,
            # robust z-score for the adaptive threshold
            "z_threshold": 2.5,
            # likes/retweets/upvotes at which a single negative post is "viral"
            "viral_engagement": 500,
            # spam mentions in one hour that count as a spam wave
            "spam_wave": 40,
            "alert_cooldown_minutes": 30,
            # forecasted sentiment index (-1..1) below which we warn
            "forecast_score_floor": 0.0,
        },
        "notifications": {
            "email": False,
            "slack": False,
            "teams": False,
            "sms": False,
            "min_severity": "high",
        },
    }


def deep_merge(base: dict, patch: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in (patch or {}).items():
        if key == "aspects" and isinstance(value, dict):
            # aspects are replaced as a whole so users can delete aspects
            result[key] = value
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class RuntimeConfig:
    KEY = "runtime_config"

    def __init__(self, db: Database, settings: Settings):
        self._db = db
        self._defaults = build_defaults(settings)
        self._lock = threading.Lock()
        stored = db.get_setting(self.KEY, {}) or {}
        self._value = deep_merge(self._defaults, stored)
        self._listeners = []

    def get(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._value)

    def subscribe(self, callback) -> None:
        self._listeners.append(callback)

    def update(self, patch: dict) -> dict:
        with self._lock:
            merged = deep_merge(self._value, patch)
            self._validate(merged)
            self._value = merged
            self._db.set_setting(self.KEY, merged)
            value = copy.deepcopy(merged)
        for callback in self._listeners:
            callback(value)
        return value

    def reset(self) -> dict:
        with self._lock:
            self._value = copy.deepcopy(self._defaults)
            self._db.set_setting(self.KEY, self._value)
            return copy.deepcopy(self._value)

    @staticmethod
    def _validate(cfg: dict) -> None:
        if not str(cfg.get("brand_name", "")).strip():
            raise ValueError("brand_name cannot be empty")
        cfg["keywords"] = [str(k).strip() for k in cfg.get("keywords", []) if str(k).strip()]
        rate = float(cfg.get("simulator_rate_per_min", 8))
        if not 0.5 <= rate <= 600:
            raise ValueError("simulator_rate_per_min must be between 0.5 and 600")
        cfg["simulator_rate_per_min"] = rate
        aspects = cfg.get("aspects") or {}
        if not isinstance(aspects, dict):
            raise ValueError("aspects must be an object of aspect -> keyword list")
        cleaned = {}
        for name, words in aspects.items():
            key = str(name).strip().lower().replace(" ", "_")
            if key:
                cleaned[key] = [str(w).strip().lower() for w in words if str(w).strip()]
        cfg["aspects"] = cleaned
        t = cfg["thresholds"]
        if not 0 < float(t["anomaly_contamination"]) <= 0.5:
            raise ValueError("anomaly_contamination must be in (0, 0.5]")
        if not 0 <= float(t["risk_alert"]) <= 100:
            raise ValueError("risk_alert must be between 0 and 100")
        if cfg["notifications"].get("min_severity") not in SEVERITIES:
            raise ValueError(f"min_severity must be one of {SEVERITIES}")
