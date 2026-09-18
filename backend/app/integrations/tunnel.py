"""Public HTTPS tunnel (Cloudflare Quick Tunnel).

Meta only accepts https redirect URIs, which a laptop running on
http://127.0.0.1 cannot provide. This starts `cloudflared tunnel --url ...`,
downloading the small binary on first use, and reports the public https URL so
the Instagram login can redirect back to this machine.

The tunnel makes the dashboard reachable from the internet for as long as it
runs, so it is started explicitly by the user and can be stopped again once the
account is connected.
"""

import asyncio
import logging
import os
import platform
import re
import stat
import subprocess
import time
from pathlib import Path

import httpx

logger = logging.getLogger("brandshield.tunnel")

URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
RELEASE = "https://github.com/cloudflare/cloudflared/releases/latest/download"
ASSETS = {
    ("windows", "amd64"): "cloudflared-windows-amd64.exe",
    ("windows", "arm64"): "cloudflared-windows-arm64.exe",
    ("linux", "amd64"): "cloudflared-linux-amd64",
    ("linux", "arm64"): "cloudflared-linux-arm64",
    ("darwin", "amd64"): "cloudflared-darwin-amd64.tgz",
    ("darwin", "arm64"): "cloudflared-darwin-arm64.tgz",
}


class TunnelError(Exception):
    pass


def _asset_name() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "amd64"
    name = ASSETS.get((system, arch))
    if not name:
        raise TunnelError(f"No cloudflared build for {system}/{arch}. Set PUBLIC_BASE_URL manually instead.")
    return name


class TunnelManager:
    """Keeps the public address alive across BrandShield restarts.

    cloudflared runs as a detached process and its address is remembered, so the
    OAuth redirect URI registered with Meta stays valid until the user stops the
    tunnel or reboots the machine.
    """

    KEY = "tunnel"

    def __init__(self, settings, db=None, on_change=None):
        self.settings = settings
        self.db = db
        self.on_change = on_change
        self.local_url = settings.public_base_url
        self.url: str | None = None
        self.pid: int | None = None
        self.state = "stopped"          # stopped | downloading | starting | running | error
        self.error: str | None = None
        self._process: subprocess.Popen | None = None

    # ------------------------------------------------------------------
    @property
    def binary(self) -> Path:
        name = _asset_name().replace(".tgz", "")
        return Path(self.settings.database_path).parent / "bin" / name

    @property
    def log_file(self) -> Path:
        return self.binary.parent / "tunnel.log"

    def status(self) -> dict:
        return {
            "state": self.state,
            "url": self.url,
            "local_url": self.local_url,
            "error": self.error,
            "binary_present": self.binary.exists(),
            "redirect_uri": f"{(self.url or self.local_url).rstrip('/')}/api/auth/instagram/callback",
        }

    def _remember(self) -> None:
        if self.db is not None:
            self.db.set_setting(self.KEY, {"url": self.url, "pid": self.pid} if self.url else {})

    def _forget(self) -> None:
        if self.db is not None:
            self.db.set_setting(self.KEY, {})

    def _apply_url(self, url: str) -> None:
        self.url = url
        self.state = "running"
        self.settings.public_base_url = url
        self.settings.frontend_url = url

    @staticmethod
    def _process_alive(pid: int | None) -> bool:
        """Is that cloudflared process still running? (checked by PID + image name)"""
        if not pid:
            return False
        try:
            if os.name == "nt":
                out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                     capture_output=True, text=True, timeout=15).stdout
                return "cloudflared" in out.lower()
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _adopt(self) -> str | None:
        """Find a tunnel this machine already runs (same log file + live process)."""
        saved = (self.db.get_setting(self.KEY, {}) or {}) if self.db is not None else {}
        pid, url = saved.get("pid"), saved.get("url")
        if url and self._process_alive(pid):
            self.pid = pid
            return url
        # the record may be gone (or stale) while cloudflared is still running
        if self.log_file.exists():
            match = URL_RE.search(self.log_file.read_text(encoding="utf-8", errors="replace"))
            if match and os.name == "nt":
                out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq cloudflared*", "/NH"],
                                     capture_output=True, text=True, timeout=15).stdout
                for line in out.splitlines():
                    if "cloudflared" in line.lower():
                        self.pid = int(line.split()[1])
                        return match.group(0)
        return None

    async def restore(self) -> None:
        """Re-attach to a tunnel still running from a previous start.

        The check is on the cloudflared process, not on an HTTP request: during
        startup this server is not accepting requests yet, so asking the tunnel
        for our own /api/health would always look dead.
        """
        url = self._adopt()
        if url:
            self._apply_url(url)
            self._remember()
            logger.info("Reusing the public address from the previous run: %s", url)
        else:
            self._forget()
        self._notify()

    async def _download(self) -> None:
        asset = _asset_name()
        if asset.endswith(".tgz"):
            raise TunnelError("On macOS install cloudflared with `brew install cloudflared`, then restart.")
        target = self.binary
        target.parent.mkdir(parents=True, exist_ok=True)
        self.state = "downloading"
        self._notify()
        logger.info("Downloading cloudflared (%s)", asset)
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            async with client.stream("GET", f"{RELEASE}/{asset}") as resp:
                if resp.status_code >= 400:
                    raise TunnelError(f"Could not download cloudflared (HTTP {resp.status_code})")
                tmp = target.with_suffix(".part")
                with tmp.open("wb") as fh:
                    async for chunk in resp.aiter_bytes():
                        fh.write(chunk)
        tmp.replace(target)
        target.chmod(target.stat().st_mode | stat.S_IEXEC)

    def _notify(self) -> None:
        if self.on_change:
            self.on_change(self.status())

    async def start(self) -> dict:
        if self.state in ("running", "starting", "downloading"):
            return self.status()
        self.error = None
        existing = self._adopt()
        if existing:
            self._apply_url(existing)
            self._remember()
            self._notify()
            return self.status()
        try:
            if not self.binary.exists():
                await self._download()
            self.state = "starting"
            self._notify()
            self.log_file.unlink(missing_ok=True)
            flags = 0
            if os.name == "nt":  # detached, so the address survives a restart
                flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            self._process = subprocess.Popen(
                [str(self.binary), "tunnel", "--url", self.local_url, "--no-autoupdate",
                 "--logfile", str(self.log_file)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                creationflags=flags, close_fds=True, start_new_session=os.name != "nt",
            )
            self.pid = self._process.pid
            url = await self._await_url(timeout=75)
            if not url:
                await self.stop()
                raise TunnelError("cloudflared did not return a public address within 75 seconds")
            self._apply_url(url)
            self._remember()
            logger.info("Public address ready: %s", url)
        except TunnelError as exc:
            self.state, self.error = "error", str(exc)
            self._notify()
            raise
        except Exception as exc:
            self.state, self.error = "error", f"{type(exc).__name__}: {exc}"
            self._notify()
            raise TunnelError(self.error) from exc
        return self.status()

    async def _await_url(self, timeout: float) -> str | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._process and self._process.poll() not in (None, 0):
                raise TunnelError(f"cloudflared exited with code {self._process.poll()}")
            if self.log_file.exists():
                match = URL_RE.search(self.log_file.read_text(encoding="utf-8", errors="replace"))
                if match:
                    return match.group(0)
            await asyncio.sleep(1)
        return None

    def _clear_url(self) -> None:
        self.url = None
        self.pid = None
        self.settings.public_base_url = self.local_url
        self.settings.frontend_url = ""

    def _terminate(self, pid: int) -> None:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=15)
            else:
                os.kill(pid, 15)
        except Exception as exc:
            logger.warning("Could not stop cloudflared (pid %s): %s", pid, exc)

    async def stop(self) -> dict:
        pid = self.pid or (self._process.pid if self._process else None)
        if pid:
            await asyncio.to_thread(self._terminate, pid)
        self._process = None
        self._clear_url()
        self._forget()
        self.state = "stopped"
        self.error = None
        self._notify()
        return self.status()
