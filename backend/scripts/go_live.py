"""Wait for the local server, then open (or reuse) the public link.

Used by start-public.bat so getting online in the morning is one double-click.
"""

import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"


def main() -> int:
    print("Waiting for the model to load (first start can take ~2 minutes)...", flush=True)
    deadline = time.time() + 420
    while time.time() < deadline:
        try:
            if httpx.get(f"{BASE}/api/health", timeout=5).json().get("model_ready"):
                break
        except Exception:
            pass
        time.sleep(4)
    else:
        print("The server did not start. Check the server window for errors.")
        return 1

    print("Model ready. Creating the public link...", flush=True)
    url = None
    for attempt in (1, 2, 3):
        try:
            data = httpx.post(f"{BASE}/api/instagram/tunnel/start", timeout=200).json()
            url = data.get("url")
        except Exception as exc:
            print(f"  attempt {attempt} failed: {exc}")
            url = None
        if url and _reachable(url):
            break
        if url:
            print(f"  {url} did not come up, retrying with a new address...")
            try:
                httpx.post(f"{BASE}/api/instagram/tunnel/stop", timeout=60)
            except Exception:
                pass
            time.sleep(3)
        url = None

    print()
    print("=" * 64)
    if url:
        print(" BrandShield AI is live")
        print()
        print(f"   On this PC : {BASE}")
        print(f"   On phone   : {url}")
        print()
        print(" Instagram redirect URI (paste in your Meta app if you reconnect):")
        print(f"   {url}/api/auth/instagram/callback")
        print()
        print(" Keep this PC on and awake. Closing the server window ends the link.")
    else:
        print(" The dashboard works on this PC:")
        print(f"   {BASE}")
        print()
        print(" The public link could not be created (Cloudflare was unreachable).")
        print(" Try again from the dashboard: YouTube/Instagram page -> Start secure address.")
    print("=" * 64)
    return 0


def _reachable(url: str) -> bool:
    for _ in range(24):
        try:
            if httpx.get(f"{url}/api/health", timeout=10).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(5)
    return False


if __name__ == "__main__":
    sys.exit(main())
