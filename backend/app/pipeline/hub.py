"""WebSocket hub that pushes live events to every connected dashboard."""

import asyncio
import json
import logging

from fastapi import WebSocket

logger = logging.getLogger("brandshield.hub")


class Hub:
    def __init__(self):
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, event_type: str, data) -> None:
        if not self._clients:
            return
        message = json.dumps({"type": event_type, "data": data}, default=str)
        async with self._lock:
            clients = list(self._clients)
        results = await asyncio.gather(*(self._send(ws, message) for ws in clients), return_exceptions=True)
        dead = [ws for ws, ok in zip(clients, results) if ok is not True]
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    @staticmethod
    async def _send(ws: WebSocket, message: str) -> bool:
        await asyncio.wait_for(ws.send_text(message), timeout=5)
        return True
