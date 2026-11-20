"""Accounts API: sign-in, sign-up, sign-out, password change and user management."""

import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.auth import COOKIE_NAME, AuthError, User, auth_enabled, get_store, session_user
from app.config import settings, write_env

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Brute-force protection: at most MAX_FAILURES failed logins / sign-ups per client per window
MAX_FAILURES = 5
WINDOW_SECONDS = 300
_failures: dict[str, deque] = defaultdict(deque)


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)


class RoleChange(BaseModel):
    role: str


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _throttle(request: Request) -> deque:
    q = _failures[_client(request)]
    cutoff = time.time() - WINDOW_SECONDS
    while q and q[0] < cutoff:
        q.popleft()
    if len(q) >= MAX_FAILURES:
        wait = int(q[0] + WINDOW_SECONDS - time.time()) + 1
        raise HTTPException(429, f"Too many failed attempts. Try again in {wait} seconds.")
    return q


def _start_session(request: Request, response: Response, user: User) -> dict:
    response.set_cookie(
        COOKIE_NAME,
        get_store(settings).make_token(user, settings.session_hours),
        max_age=int(settings.session_hours * 3600),
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return {"authenticated": True, "username": user.username, "role": user.role}


def _current(request: Request) -> User:
    user = session_user(settings, request.scope)
    if user is None:
        raise HTTPException(401, "Login required")
    return user


def _require_admin(request: Request) -> User:
    user = _current(request)
    if user.role != "admin":
        raise HTTPException(403, "Only admins can manage users.")
    return user


@router.get("/session")
def session(request: Request):
    """Tell the dashboard whether a login is needed and who is logged in."""
    if not auth_enabled(settings):
        return {"auth_enabled": False, "authenticated": True, "username": None, "role": "admin",
                "signup_allowed": False}
    user = session_user(settings, request.scope)
    return {"auth_enabled": True, "authenticated": user is not None,
            "username": user.username if user else None, "role": user.role if user else None,
            "signup_allowed": settings.allow_signup}


@router.post("/login")
def login(body: Credentials, request: Request, response: Response):
    if not auth_enabled(settings):
        return {"authenticated": True, "username": None, "role": "admin"}
    failures = _throttle(request)
    user = get_store(settings).authenticate(body.username.strip(), body.password)
    if user is None:
        failures.append(time.time())
        raise HTTPException(401, "Incorrect username or password.")
    failures.clear()
    return _start_session(request, response, user)


@router.post("/register")
def register(body: Credentials, request: Request, response: Response):
    """Create a read-only viewer account and sign it in."""
    if not auth_enabled(settings) or not settings.allow_signup:
        raise HTTPException(403, "Sign-up is disabled. Ask an admin for an account.")
    failures = _throttle(request)
    try:
        user = get_store(settings).create(body.username, body.password, role="viewer")
    except AuthError as exc:
        failures.append(time.time())  # also slows down username probing
        raise HTTPException(422, str(exc))
    return _start_session(request, response, user)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"authenticated": False}


@router.post("/password")
def change_password(body: PasswordChange, request: Request, response: Response):
    user = _current(request)
    store = get_store(settings)
    if store.authenticate(user.username, body.current_password) is None:
        raise HTTPException(401, "Current password is incorrect.")
    try:
        store.set_password(user.username, body.new_password)
    except AuthError as exc:
        raise HTTPException(422, str(exc))
    if user.username.lower() == settings.admin_username.lower():
        # The .env admin is re-synced from .env on start-up, so keep .env in step
        write_env({"ADMIN_PASSWORD": body.new_password})
        settings.admin_password = body.new_password
    # Old sessions die with the old hash; give this browser a fresh one
    return _start_session(request, response, store.get(user.username))


@router.get("/users")
def list_users(request: Request):
    _require_admin(request)
    return {"users": [u.public() for u in get_store(settings).list()]}


@router.put("/users/{username}")
def set_role(username: str, body: RoleChange, request: Request):
    _require_admin(request)
    if username.lower() == settings.admin_username.lower() and body.role != "admin":
        raise HTTPException(422, "The main admin account (from .env) always stays admin.")
    try:
        return get_store(settings).set_role(username, body.role).public()
    except KeyError:
        raise HTTPException(404, "User not found")
    except AuthError as exc:
        raise HTTPException(422, str(exc))


@router.delete("/users/{username}")
def delete_user(username: str, request: Request):
    me = _require_admin(request)
    if username.lower() == me.username.lower():
        raise HTTPException(422, "You cannot delete your own account.")
    if username.lower() == settings.admin_username.lower():
        raise HTTPException(422, "The main admin account (from .env) cannot be deleted.")
    try:
        get_store(settings).delete(username)
    except KeyError:
        raise HTTPException(404, "User not found")
    except AuthError as exc:
        raise HTTPException(422, str(exc))
    return {"deleted": username}
