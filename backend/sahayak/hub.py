"""WebSocket hub — broadcasts realtime events to rooms.

Rooms: 'admin' (sees everything) and 'center:<id>' (sees its own cases/alerts).
A connection receives an event if its rooms intersect the event's targets.
"""
from __future__ import annotations

from fastapi import WebSocket


class Hub:
    def __init__(self):
        self._conns: list[tuple[WebSocket, set[str]]] = []

    async def connect(self, ws: WebSocket, rooms: set[str]) -> None:
        await ws.accept()
        self._conns.append((ws, rooms))

    def disconnect(self, ws: WebSocket) -> None:
        self._conns = [(w, r) for (w, r) in self._conns if w is not ws]

    async def broadcast(self, targets: set[str], event: str, data: dict) -> None:
        msg = {"event": event, "data": data}
        dead = []
        for ws, rooms in list(self._conns):
            if rooms & targets:
                try:
                    await ws.send_json(msg)
                except Exception:
                    dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def count(self) -> int:
        return len(self._conns)
