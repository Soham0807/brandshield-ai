"""Login / logout / session endpoints for the dashboard."""

import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.auth import COOKIE_NAME, auth_enabled, check_credentials, make_token, session_user
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Brute-force protection: at most MAX_FAILURES failed logins per client per window
MAX_FAILURES = 5
WINDOW_SECONDS = 300
_failures: dict[str, deque] = defaultdict(deque)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _recent_failures(client: str) -> deque:
    q = _failures[client]
    cutoff = time.time() - WINDOW_SECONDS
    while q and q[0] < cutoff:
        q.popleft()
    return q


@router.get("/session")
def session(request: Request):
    """Tell the dashboard whether a login is needed and who is logged in."""
    if not auth_enabled(settings):
        return {"auth_enabled": False, "authenticated": True, "username": None}
    user = session_user(settings, request.scope)
    return {"auth_enabled": True, "authenticated": user is not None, "username": user}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response):
    if not auth_enabled(settings):
        return {"authenticated": True, "username": None}
    client = _client(request)
    failures = _recent_failures(client)
    if len(failures) >= MAX_FAILURES:
        wait = int(failures[0] + WINDOW_SECONDS - time.time()) + 1
        raise HTTPException(429, f"Too many failed attempts. Try again in {wait} seconds.")
    if not check_credentials(settings, body.username, body.password):
        failures.append(time.time())
        raise HTTPException(401, "Incorrect username or password.")
    failures.clear()
    response.set_cookie(
        COOKIE_NAME,
        make_token(settings, body.username.strip()),
        max_age=int(settings.session_hours * 3600),
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return {"authenticated": True, "username": body.username.strip()}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"authenticated": False}
