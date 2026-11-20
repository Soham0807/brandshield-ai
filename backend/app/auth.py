"""Dashboard login: one admin account, signed session cookie.

Enabled only when ADMIN_PASSWORD is set in backend/.env. The cookie holds
``username|expiry|signature`` where the signature is an HMAC-SHA256 keyed by a
hash of the password, so changing the password logs every session out. The
cookie is HttpOnly (JavaScript cannot read it) and SameSite=Lax.

``AuthMiddleware`` is a pure ASGI middleware so it guards both the REST API and
the live WebSocket. Static files (the React app itself) are always served; the
React app shows the login screen when the API answers 401.
"""

import hashlib
import hmac
import time
from http.cookies import SimpleCookie

from starlette.responses import JSONResponse

COOKIE_NAME = "brandshield_session"

# API paths reachable without a session
PUBLIC_PATHS = {"/api/health", "/api/auth/login", "/api/auth/logout", "/api/auth/session"}
# Instagram redirects the browser back here, possibly through the tunnel host
# where the session cookie does not exist; the OAuth state check protects it.
PUBLIC_PREFIXES = ("/api/auth/instagram/",)


def auth_enabled(settings) -> bool:
    return bool(settings.admin_password)


def _key(settings) -> bytes:
    return hashlib.sha256(("brandshield-session:" + settings.admin_password).encode()).digest()


def _sign(settings, payload: str) -> str:
    return hmac.new(_key(settings), payload.encode(), hashlib.sha256).hexdigest()


def check_credentials(settings, username: str, password: str) -> bool:
    user_ok = hmac.compare_digest(username.strip().encode(), settings.admin_username.encode())
    pass_ok = hmac.compare_digest(password.encode(), settings.admin_password.encode())
    return user_ok and pass_ok


def make_token(settings, username: str) -> str:
    expiry = int(time.time() + settings.session_hours * 3600)
    payload = f"{username}|{expiry}"
    return f"{payload}|{_sign(settings, payload)}"


def verify_token(settings, token: str | None) -> str | None:
    """Return the username for a valid, unexpired token, else None."""
    if not token:
        return None
    try:
        username, expiry, signature = token.rsplit("|", 2)
        expiry_ts = int(expiry)
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(settings, f"{username}|{expiry}")):
        return None
    if expiry_ts < time.time():
        return None
    return username


def _cookie_from_scope(scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"cookie":
            jar = SimpleCookie()
            try:
                jar.load(value.decode("latin-1"))
            except Exception:
                return None
            morsel = jar.get(COOKIE_NAME)
            return morsel.value if morsel else None
    return None


def session_user(settings, scope) -> str | None:
    return verify_token(settings, _cookie_from_scope(scope))


def is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES) or not (
        path.startswith("/api/") or path.startswith("/ws")
    )


class AuthMiddleware:
    def __init__(self, app, settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket") or not auth_enabled(self.settings):
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        if is_public(path) or session_user(self.settings, scope):
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            # Refuse the handshake (policy violation)
            await send({"type": "websocket.close", "code": 1008})
            return
        response = JSONResponse({"detail": "Login required"}, status_code=401)
        await response(scope, receive, send)
