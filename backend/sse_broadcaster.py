"""
SSE Broadcaster — fan-out push to all connected dashboard clients.
Uses asyncio.Queue per subscriber so each client gets every event.
"""
import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator


class SSEBroadcaster:
    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def broadcast(self, event_type: str, job_id: str, data: dict):
        payload = {
            "event": event_type,
            "job_id": job_id,
            "data": data,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        dead = []
        for q in self._subscribers:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.unsubscribe(q)

    async def stream(self, q: asyncio.Queue) -> AsyncGenerator[str, None]:
        try:
            while True:
                event = await asyncio.wait_for(q.get(), timeout=30)
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.TimeoutError:
            yield ": keep-alive\n\n"
        except asyncio.CancelledError:
            return


broadcaster = SSEBroadcaster()
