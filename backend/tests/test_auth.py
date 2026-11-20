"""Unit tests for accounts: password hashing, users and roles, sessions, middleware rules."""

import pytest

from app.auth import (AuthError, UserStore, hash_password, is_public, verify_password,
                      viewer_may)


@pytest.fixture
def store(tmp_path):
    s = UserStore(tmp_path / "users.db")
    s.ensure_admin("admin", "Admin#2025")
    return s


# ---- passwords

def test_password_hash_verifies_and_is_salted():
    h1, h2 = hash_password("Secret#123"), hash_password("Secret#123")
    assert h1 != h2, "each hash should use a fresh salt"
    assert verify_password("Secret#123", h1)
    assert not verify_password("wrong", h1)
    assert "Secret#123" not in h1


def test_malformed_hash_is_rejected():
    assert not verify_password("x", "not-a-hash")


# ---- sign-up and roles

def test_signup_creates_viewer(store):
    user = store.create("priya", "Viewer#2025")
    assert user.role == "viewer"
    assert store.authenticate("priya", "Viewer#2025").username == "priya"
    assert store.authenticate("priya", "wrong") is None


def test_usernames_are_case_insensitive_and_unique(store):
    store.create("Rahul", "Viewer#2025")
    with pytest.raises(AuthError):
        store.create("rahul", "Other#2025")


@pytest.mark.parametrize("username,password", [
    ("ab", "Viewer#2025"),           # username too short
    ("bad name", "Viewer#2025"),     # space in username
    ("okname", "short1"),            # password too short
    ("okname", "onlyletters"),       # no digits/symbols
    ("okname", "1234567890"),        # digits only
])
def test_weak_credentials_are_refused(store, username, password):
    with pytest.raises(AuthError):
        store.create(username, password)


def test_last_admin_cannot_be_demoted_or_deleted(store):
    with pytest.raises(AuthError):
        store.set_role("admin", "viewer")
    with pytest.raises(AuthError):
        store.delete("admin")


def test_viewer_can_be_promoted_and_deleted(store):
    store.create("anita", "Viewer#2025")
    assert store.set_role("anita", "admin").role == "admin"
    store.delete("anita")
    assert store.get("anita") is None


def test_env_admin_password_is_synced(store):
    store.ensure_admin("admin", "Changed#2026")
    assert store.authenticate("admin", "Changed#2026") is not None
    assert store.authenticate("admin", "Admin#2025") is None


# ---- sessions

def test_valid_token_round_trips(store):
    user = store.get("admin")
    assert store.verify_token(store.make_token(user, 1)).username == "admin"


def test_tampered_token_is_rejected(store):
    store.create("mallory", "Viewer#2025")
    _, expiry, sig = store.make_token(store.get("mallory"), 1).rsplit("|", 2)
    assert store.verify_token(f"admin|{expiry}|{sig}") is None


def test_expired_token_is_rejected(store):
    assert store.verify_token(store.make_token(store.get("admin"), -1)) is None


def test_password_change_ends_old_sessions(store):
    store.create("kiran", "Viewer#2025")
    token = store.make_token(store.get("kiran"), 1)
    store.set_password("kiran", "NewPass#2026")
    assert store.verify_token(token) is None


def test_deleted_user_session_is_rejected(store):
    store.create("temp", "Viewer#2025")
    token = store.make_token(store.get("temp"), 1)
    store.delete("temp")
    assert store.verify_token(token) is None


def test_garbage_token_is_rejected(store):
    assert store.verify_token("not-a-token") is None
    assert store.verify_token(None) is None


# ---- middleware rules

def test_public_and_protected_paths():
    assert is_public("/api/health")
    assert is_public("/api/auth/login")
    assert is_public("/api/auth/register")
    assert is_public("/api/auth/instagram/callback")
    assert is_public("/")                # the React app itself
    assert is_public("/assets/app.js")
    assert not is_public("/api/mentions")
    assert not is_public("/api/auth/users")
    assert not is_public("/ws")


def test_viewers_are_read_only():
    assert viewer_may("GET", "/api/mentions")
    assert viewer_may("POST", "/api/analyze")
    assert viewer_may("POST", "/api/auth/password")
    assert not viewer_may("PUT", "/api/settings")
    assert not viewer_may("POST", "/api/simulator/crisis")
    assert not viewer_may("DELETE", "/api/instagram/pages/x")
