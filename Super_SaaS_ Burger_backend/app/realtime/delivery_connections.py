from __future__ import annotations

import asyncio
from typing import Dict, Tuple

from fastapi import WebSocket

ConnectionKey = Tuple[int, int]


class DeliveryConnectionRegistry:
    def __init__(self) -> None:
        self._connections: Dict[ConnectionKey, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def set(self, tenant_id: int, delivery_user_id: int, websocket: WebSocket) -> None:
        key = (tenant_id, delivery_user_id)
        async with self._lock:
            self._connections[key] = websocket

    async def remove(self, tenant_id: int, delivery_user_id: int, websocket: WebSocket | None = None) -> None:
        key = (tenant_id, delivery_user_id)
        async with self._lock:
            existing = self._connections.get(key)
            if existing is None:
                return
            if websocket is not None and existing is not websocket:
                return
            self._connections.pop(key, None)

    async def get(self, tenant_id: int, delivery_user_id: int) -> WebSocket | None:
        async with self._lock:
            return self._connections.get((tenant_id, delivery_user_id))


delivery_connections = DeliveryConnectionRegistry()
