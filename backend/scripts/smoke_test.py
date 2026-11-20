"""Run the report's API test cases against a running BrandShield server.

Usage (server running on http://127.0.0.1:8000):
    python -m scripts.smoke_test
Prints one line per test case: PASS / FAIL with what was observed.
Tests that change data use throw-away inputs and clean up after themselves.
"""

import asyncio
import io
import json
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"
results = []
SESSION_COOKIE = None


def record(tc, name, ok, detail):
    results.append((tc, name, ok, detail))
    print(f"{tc:6} {'PASS' if ok else 'FAIL'}  {name}: {detail}", flush=True)


def main():
    c = httpx.Client(base_url=BASE, timeout=120)

    r = c.get("/api/health")
    record("TC-01", "Health check", r.status_code == 200 and r.json().get("status") == "ok", f"{r.status_code} {r.json()}")

    # Dashboard login (only when ADMIN_PASSWORD is set in backend/.env)
    from app.config import settings
    if settings.admin_password:
        r = c.get("/api/mentions")
        record("TC-32", "API refused without login", r.status_code == 401, f"{r.status_code}")
        r = c.post("/api/auth/login", json={"username": settings.admin_username, "password": "wrong-password"})
        record("TC-33", "Wrong password refused", r.status_code == 401, f"{r.status_code}")
        r = c.post("/api/auth/login", json={"username": settings.admin_username, "password": settings.admin_password})
        record("TC-34", "Login with correct password", r.status_code == 200 and "brandshield_session" in c.cookies,
               f"{r.status_code}, session cookie {'set' if 'brandshield_session' in c.cookies else 'missing'}")
    global SESSION_COOKIE
    SESSION_COOKIE = c.cookies.get("brandshield_session")

    a = c.post("/api/analyze", json={"text": ""}).status_code
    b = c.post("/api/analyze", json={"text": "x" * 5001}).status_code
    record("TC-03", "Text length validation", a == 422 and b == 422, f"empty -> {a}, 5001 chars -> {b}")

    r = c.post("/api/analyze", json={"text": "Worst coffee ever 😡"}).json()
    s = r["sentiment"]
    record("TC-04", "English negative comment", s["label"] == "negative" and s["score"] < 0, f"{s['label']}, score {s['score']}")

    r = c.post("/api/analyze", json={"text": "khana ekdum bekar tha"}).json()
    s = r["sentiment"]
    lp = s.get("lexicon_polarity")
    record("TC-05", "Hinglish negative comment", s["label"] == "negative" and (lp is not None and lp < 0),
           f"{s['label']}, lexicon polarity {lp}")

    r = c.post("/api/analyze", json={"text": "the product is great but delivery was late"}).json()
    asp = {a["aspect"]: a["sentiment"] for a in r["aspects"]}
    record("TC-06", "Mixed opinion, per-topic sentiment", asp.get("delivery") == "negative" and asp.get("product") == "positive",
           f"topics {asp}")

    r = c.post("/api/ingest", json={"items": []})
    record("TC-10", "Empty ingest", r.status_code == 422, f"{r.status_code}")

    before = c.get("/api/system/metrics").json()["duplicates_total"]
    item = {"text": f"smoke test duplicate {time.time()}", "source": "smoketest", "external_id": f"smoke-{time.time()}"}
    c.post("/api/ingest", json={"items": [item]})
    c.post("/api/ingest", json={"items": [item]})
    time.sleep(4)
    stored = c.get("/api/mentions", params={"source": "smoketest", "limit": 50}).json()["total"]
    after = c.get("/api/system/metrics").json()["duplicates_total"]
    record("TC-11", "Duplicate ingest", stored == 1 and after >= before + 1, f"stored {stored}, duplicates +{after - before}")

    utf16 = c.post("/api/ingest/csv", files={"file": ("x.csv", "text\nhello".encode("utf-16"), "text/csv")})
    nocol = c.post("/api/ingest/csv", files={"file": ("y.csv", b"body,date\nhello,2026-01-01", "text/csv")})
    record("TC-13", "Invalid CSV", utf16.status_code == 400 and nocol.status_code == 400,
           f"UTF-16 -> {utf16.status_code}, no text column -> {nocol.status_code} ({nocol.json().get('detail')})")

    r1 = c.put("/api/settings", json={"brand_name": "  "}).status_code
    r2 = c.put("/api/settings", json={"thresholds": {"anomaly_contamination": 0.9}}).status_code
    r3 = c.put("/api/settings", json={"notifications": {"min_severity": "urgent"}}).status_code
    record("TC-16", "Settings validation", (r1, r2, r3) == (422, 422, 422), f"blank brand {r1}, contamination 0.9 {r2}, severity 'urgent' {r3}")

    fc = c.get("/api/forecast").json()
    method = (fc.get("sentiment") or {}).get("method")
    record("TC-20", "Forecast available", method in ("prophet", "holt", "insufficient_data"), f"method {method}, {len(fc.get('history') or [])} hours of history")

    alerts = c.get("/api/alerts", params={"limit": 1}).json()["items"]
    if alerts:
        aid, old = alerts[0]["id"], alerts[0]["status"]
        ok_code = c.post(f"/api/alerts/{aid}/acknowledge").status_code
        c.post(f"/api/alerts/{aid}/{ {'open': 'reopen', 'dismissed': 'dismiss', 'acknowledged': 'acknowledge'}[old] }")
    else:
        ok_code = None
    missing = c.post("/api/alerts/999999999/acknowledge").status_code
    record("TC-22", "Alert actions", ok_code in (200, None) and missing == 404, f"acknowledge -> {ok_code}, unknown id -> {missing}")

    r = c.put("/api/keys", json={"youtube_api_key": "x"}, headers={"X-Forwarded-For": "1.2.3.4"})
    record("TC-24", "Remote setup blocked", r.status_code == 403, f"{r.status_code}")

    r = c.post("/api/youtube/channels", json={"query": "@no_such_channel_brandshield_xyz", "set_brand": False})
    record("TC-26", "Unknown YouTube channel", r.status_code in (422, 503), f"{r.status_code} {str(r.json().get('detail'))[:70]}")

    r = c.get("/api/instagram/status").text
    record("TC-31", "Token privacy", "access_token" not in r, "no access_token field in response" if "access_token" not in r else "token field present")

    asyncio.run(websocket_check())

    # clean up the smoke-test mention
    import sqlite3
    from pathlib import Path
    db = sqlite3.connect(Path(__file__).resolve().parent.parent / "data" / "brandshield.db")
    db.execute("DELETE FROM mentions WHERE source = 'smoketest'")
    db.commit()

    passed = sum(1 for *_, ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} passed", flush=True)
    return 0 if passed == len(results) else 1


async def websocket_check():
    import websockets
    headers = {"Cookie": f"brandshield_session={SESSION_COOKIE}"} if SESSION_COOKIE else {}
    try:  # websockets >= 14
        conn = websockets.connect(BASE.replace("http", "ws") + "/ws", additional_headers=headers)
    except TypeError:
        conn = websockets.connect(BASE.replace("http", "ws") + "/ws", extra_headers=headers)
    async with conn as ws:
        first = json.loads(await asyncio.wait_for(ws.recv(), 10))
        await ws.send("ping")
        pong = None
        for _ in range(20):
            msg = json.loads(await asyncio.wait_for(ws.recv(), 10))
            if msg.get("type") == "pong":
                pong = msg
                break
    record("TC-28", "WebSocket", first.get("type") == "status" and pong is not None, f"first '{first.get('type')}', then {'pong' if pong else 'no pong'}")


if __name__ == "__main__":
    sys.exit(main())
