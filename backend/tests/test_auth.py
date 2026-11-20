"""Unit tests for the dashboard login (session tokens and the middleware's public paths)."""

from types import SimpleNamespace

from app.auth import check_credentials, is_public, make_token, verify_token


def _settings(password="s3cret", hours=1.0):
    return SimpleNamespace(admin_username="admin", admin_password=password, session_hours=hours)


def test_valid_token_round_trips():
    s = _settings()
    assert verify_token(s, make_token(s, "admin")) == "admin"


def test_tampered_token_is_rejected():
    s = _settings()
    user, expiry, sig = make_token(s, "admin").rsplit("|", 2)
    assert verify_token(s, f"attacker|{expiry}|{sig}") is None


def test_expired_token_is_rejected():
    s = _settings(hours=-1)
    assert verify_token(s, make_token(s, "admin")) is None


def test_changing_password_invalidates_sessions():
    token = make_token(_settings("old"), "admin")
    assert verify_token(_settings("new"), token) is None


def test_garbage_token_is_rejected():
    assert verify_token(_settings(), "not-a-token") is None
    assert verify_token(_settings(), None) is None


def test_credentials_check():
    s = _settings()
    assert check_credentials(s, "admin", "s3cret")
    assert not check_credentials(s, "admin", "wrong")
    assert not check_credentials(s, "root", "s3cret")


def test_public_and_protected_paths():
    assert is_public("/api/health")
    assert is_public("/api/auth/login")
    assert is_public("/api/auth/instagram/callback")
    assert is_public("/")                # the React app itself
    assert is_public("/assets/app.js")
    assert not is_public("/api/mentions")
    assert not is_public("/ws")
