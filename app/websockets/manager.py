import json
from fastapi import WebSocket

from app.core import async_bridge


class ConnectionManager:
    def __init__(self):
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket):
        self._connections.discard(websocket)

    async def _broadcast(self, message: dict):
        payload = json.dumps(message)
        dead = []
        for ws in list(self._connections):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)

    def broadcast_from_thread(self, message: dict):
        async_bridge.run_coroutine(self._broadcast(message))


manager = ConnectionManager()