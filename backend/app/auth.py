"""Dashboard accounts: users, roles, sign-up and signed session cookies.

Enabled when ADMIN_PASSWORD is set in backend/.env. That account is created as
the first **admin** on start-up; people who sign up become **viewers**
(read-only). Admins can promote, demote and delete users.

Storage: ``data/users.db`` (SQLite), separate from the mention database so the
real instance and the demo instance share the same accounts. Passwords are
hashed with PBKDF2-HMAC-SHA256 (200 000 iterations, 16-byte random salt).

Session cookie: ``username|expiry|signature``. The signature is HMAC-SHA256
over the payload, keyed by a server secret (``data/session.key``) combined with
the user's password hash, so changing a password or deleting a user ends their
sessions. The cookie is HttpOnly and SameSite=Lax.

``AuthMiddleware`` is pure ASGI so it guards the REST API and the WebSocket.
"""

import hashlib
import hmac
import re
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from http.cookies import SimpleCookie
from pathlib import Path

from starlette.responses import JSONResponse

COOKIE_NAME = "brandshield_session"
ROLES = ("admin", "viewer")
PBKDF2_ITERATIONS = 200_000
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")
MIN_PASSWORD = 8

# API paths reachable without a session
PUBLIC_PATHS = {"/api/health", "/api/auth/login", "/api/auth/logout", "/api/auth/session", "/api/auth/register"}
# Instagram redirects the browser back here, possibly through the tunnel host
# where the session cookie does not exist; the OAuth state check protects it.
PUBLIC_PREFIXES = ("/api/auth/instagram/",)
# Write calls a viewer may still make (they change nothing shared)
VIEWER_WRITE_ALLOWED = {"/api/analyze", "/api/auth/logout", "/api/auth/password"}
READ_METHODS = {"GET", "HEAD", "OPTIONS"}


class AuthError(ValueError):
    """A user-facing validation error (bad username, weak password ...)."""


@dataclass
class User:
    username: str
    role: str
    password_hash: str
    created_at: float
    last_login: float | None = None

    def public(self) -> dict:
        return {"username": self.username, "role": self.role,
                "created_at": self.created_at, "last_login": self.last_login}


# ---------------------------------------------------------------- passwords

def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def validate_new_credentials(username: str, password: str) -> None:
    if not USERNAME_RE.match(username or ""):
        raise AuthError("Username must be 3-32 characters: letters, digits, '.', '_' or '-'.")
    validate_password(password)


def validate_password(password: str) -> None:
    if len(password or "") < MIN_PASSWORD:
        raise AuthError(f"Password must be at least {MIN_PASSWORD} characters.")
    if password.isdigit() or password.isalpha():
        raise AuthError("Password must mix letters with digits or symbols.")


# ---------------------------------------------------------------- user store

class UserStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY COLLATE NOCASE,
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at REAL NOT NULL,
                last_login REAL)""")
        key_file = self.path.parent / "session.key"
        if not key_file.exists():
            key_file.write_text(secrets.token_hex(32), encoding="utf-8")
        self.secret = bytes.fromhex(key_file.read_text(encoding="utf-8").strip())

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def get(self, username: str) -> User | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()
        return User(**dict(row)) if row else None

    def list(self) -> list[User]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM users ORDER BY role, username COLLATE NOCASE").fetchall()
        return [User(**dict(r)) for r in rows]

    def count_admins(self) -> int:
        with self._connect() as db:
            return db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]

    def create(self, username: str, password: str, role: str = "viewer") -> User:
        username = username.strip()
        validate_new_credentials(username, password)
        if role not in ROLES:
            raise AuthError(f"Role must be one of {', '.join(ROLES)}.")
        with self._lock, self._connect() as db:
            if db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
                raise AuthError("That username is already taken.")
            db.execute("INSERT INTO users (username, role, password_hash, created_at) VALUES (?, ?, ?, ?)",
                       (username, role, hash_password(password), time.time()))
        return self.get(username)

    def ensure_admin(self, username: str, password: str) -> None:
        """Create the .env admin on first start; later starts keep it in sync with .env."""
        user = self.get(username)
        if user is None:
            with self._connect() as db:
                db.execute("INSERT INTO users (username, role, password_hash, created_at) VALUES (?, 'admin', ?, ?)",
                           (username, hash_password(password), time.time()))
        elif user.role != "admin" or not verify_password(password, user.password_hash):
            with self._connect() as db:
                db.execute("UPDATE users SET role = 'admin', password_hash = ? WHERE username = ?",
                           (hash_password(password), username))

    def authenticate(self, username: str, password: str) -> User | None:
        user = self.get(username or "")
        if user is None:
            verify_password(password, hash_password("timing-equaliser"))  # same cost for unknown users
            return None
        if not verify_password(password, user.password_hash):
            return None
        with self._connect() as db:
            db.execute("UPDATE users SET last_login = ? WHERE username = ?", (time.time(), user.username))
        return user

    def set_password(self, username: str, new_password: str) -> None:
        validate_password(new_password)
        with self._connect() as db:
            db.execute("UPDATE users SET password_hash = ? WHERE username = ?",
                       (hash_password(new_password), username))

    def set_role(self, username: str, role: str) -> User:
        if role not in ROLES:
            raise AuthError(f"Role must be one of {', '.join(ROLES)}.")
        user = self.get(username)
        if user is None:
            raise KeyError(username)
        if user.role == "admin" and role != "admin" and self.count_admins() <= 1:
            raise AuthError("At least one admin must remain.")
        with self._connect() as db:
            db.execute("UPDATE users SET role = ? WHERE username = ?", (role, user.username))
        return self.get(user.username)

    def delete(self, username: str) -> None:
        user = self.get(username)
        if user is None:
            raise KeyError(username)
        if user.role == "admin" and self.count_admins() <= 1:
            raise AuthError("At least one admin must remain.")
        with self._connect() as db:
            db.execute("DELETE FROM users WHERE username = ?", (user.username,))

    # ---- sessions

    def _sign(self, user: User, payload: str) -> str:
        key = hmac.new(self.secret, user.password_hash.encode(), hashlib.sha256).digest()
        return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()

    def make_token(self, user: User, hours: float) -> str:
        payload = f"{user.username}|{int(time.time() + hours * 3600)}"
        return f"{payload}|{self._sign(user, payload)}"

    def verify_token(self, token: str | None) -> User | None:
        """Return the user for a valid, unexpired token, else None."""
        if not token:
            return None
        try:
            username, expiry, signature = token.rsplit("|", 2)
            expiry_ts = int(expiry)
        except ValueError:
            return None
        if expiry_ts < time.time():
            return None
        user = self.get(username)
        if user is None or not hmac.compare_digest(signature, self._sign(user, f"{username}|{expiry}")):
            return None
        return user


# ---------------------------------------------------------------- helpers

_store: UserStore | None = None


def auth_enabled(settings) -> bool:
    return bool(settings.admin_password)


def get_store(settings) -> UserStore:
    global _store
    if _store is None or _store.path != Path(settings.users_db_path):
        _store = UserStore(settings.users_db_path)
        if settings.admin_password:
            _store.ensure_admin(settings.admin_username, settings.admin_password)
    return _store


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


def session_user(settings, scope) -> User | None:
    return get_store(settings).verify_token(_cookie_from_scope(scope))


def is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES) or not (
        path.startswith("/api/") or path.startswith("/ws")
    )


def viewer_may(method: str, path: str) -> bool:
    """Viewers are read-only: GET everything, but only harmless write calls."""
    return method.upper() in READ_METHODS or path in VIEWER_WRITE_ALLOWED


class AuthMiddleware:
    def __init__(self, app, settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket") or not auth_enabled(self.settings):
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        if is_public(path):
            return await self.app(scope, receive, send)
        user = session_user(self.settings, scope)
        if user is None:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})  # policy violation
                return
            return await JSONResponse({"detail": "Login required"}, status_code=401)(scope, receive, send)
        if scope["type"] == "http" and user.role != "admin" and not viewer_may(scope["method"], path):
            return await JSONResponse(
                {"detail": "Your account is read-only (viewer). Ask an admin for edit access."},
                status_code=403)(scope, receive, send)
        scope.setdefault("state", {})["user"] = user
        return await self.app(scope, receive, send)
