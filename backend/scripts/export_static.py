"""Export a snapshot of the live dashboard into a single JSON file.

The React app can then run as a *static* site (Hugging Face Static Space, GitHub
Pages, Netlify…) with no backend at all: every chart, aspect breakdown, mention
and alert is served from the snapshot.

Usage (with the server running):

    python -m scripts.export_static                     # -> frontend/public/snapshot.json
    python -m scripts.export_static --base http://127.0.0.1:8000
"""

import argparse
import json
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parent.parent
OUTPUT = BACKEND.parent / "frontend" / "public" / "snapshot.json"

WINDOWS = [6, 24, 72, 168, 720]

# every API path the dashboard asks for, so the static build finds a match
PATHS: list[str] = [
    "/health", "/status", "/risk", "/forecast", "/settings", "/keys",
    "/mentions/facets", "/system/metrics", "/system/evaluation",
    "/youtube/status", "/youtube/videos?limit=60",
    "/instagram/status", "/instagram/media?limit=60",
    "/alerts?limit=200", "/alerts?status=open&limit=200",
    "/alerts?status=open&limit=1", "/alerts?status=open&limit=4",
    "/alerts?status=acknowledged&limit=200", "/alerts?status=dismissed&limit=200",
    "/mentions?limit=12", "/mentions?limit=30&offset=0", "/mentions?limit=50",
    "/mentions?sort=newest&limit=30&offset=0",
]
for hours in WINDOWS:
    PATHS += [f"/overview?hours={hours}", f"/trends?hours={hours}", f"/aspects?hours={hours}"]
for hours in (6, 24, 48, 72):
    PATHS.append(f"/anomalies?hours={hours}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8000", help="running BrandShield server")
    parser.add_argument("--out", default=str(OUTPUT))
    parser.add_argument("--mentions", type=int, default=400, help="how many mentions to embed")
    args = parser.parse_args()

    snapshot: dict[str, object] = {}
    failed: list[str] = []

    with httpx.Client(base_url=args.base.rstrip("/") + "/api", timeout=60) as client:
        try:
            client.get("/health")
        except httpx.HTTPError:
            raise SystemExit(f"No server at {args.base} — start it first, then re-run this export.")

        for path in PATHS:
            try:
                resp = client.get(path)
                if resp.status_code == 200:
                    snapshot[path] = resp.json()
                else:
                    failed.append(f"{path} ({resp.status_code})")
            except httpx.HTTPError as exc:
                failed.append(f"{path} ({type(exc).__name__})")

        # a pool of mentions the static build can filter client-side
        pool = client.get(f"/mentions?limit={args.mentions}&sort=newest").json()
        snapshot["__mentions__"] = pool.get("items", [])
        # per-video / per-post comment threads used by the YouTube + Instagram pages
        threads: dict[str, list] = {}
        for source, key in (("/youtube/videos?limit=60", "id"), ("/instagram/media?limit=60", "id")):
            for item in (snapshot.get(source) or {}).get("items", []):
                parent = item.get(key)
                if not parent:
                    continue
                data = client.get(f"/mentions?parent_id={parent}&limit=200").json()
                if data.get("items"):
                    threads[parent] = data["items"]
        snapshot["__threads__"] = threads

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    size_mb = out.stat().st_size / 1_000_000
    overview = snapshot.get("/overview?hours=720") or snapshot.get("/overview?hours=24") or {}
    print(f"Snapshot written to {out}  ({size_mb:.1f} MB)")
    print(f"  brand      : {overview.get('brand_name')}")
    print(f"  mentions   : {len(snapshot['__mentions__'])} embedded")
    print(f"  threads    : {len(snapshot['__threads__'])} videos/posts with comments")
    print(f"  endpoints  : {len(snapshot) - 2} captured")
    if failed:
        print(f"  skipped    : {', '.join(failed)}")


if __name__ == "__main__":
    main()
