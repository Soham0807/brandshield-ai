"""Unit tests for the crisis opening burst of the simulator."""

from datetime import datetime, timedelta, timezone

from app.collectors.simulator import MentionSimulator

NOW = datetime(2025, 3, 1, 12, 0, tzinfo=timezone.utc)


def test_no_burst_without_active_crisis():
    assert MentionSimulator(seed=1).opening_burst("Brand", 20, NOW) == []


def test_burst_is_recent_and_mostly_negative():
    sim = MentionSimulator(seed=1)
    sim.start_crisis("delivery", 10, 1.0, NOW)
    burst = sim.opening_burst("Brand", 20, NOW, minutes=5)
    # 20/min x 3.5 crisis multiplier / 1.1 seasonal average x 5 min ~ 318
    assert 200 < len(burst) < 450
    assert all(NOW - timedelta(minutes=5) <= m["created_at"] < NOW for m in burst)
    negative = sum(m["true_label"] == "negative" for m in burst) / len(burst)
    assert negative > 0.75
