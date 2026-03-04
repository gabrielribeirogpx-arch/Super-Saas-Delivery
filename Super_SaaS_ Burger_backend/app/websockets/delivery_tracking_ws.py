from collections import defaultdict

from fastapi import WebSocket


class DeliveryConnectionManager:
    def __init__(self):
        self.active_connections = defaultdict(list)

    async def connect(self, order_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[order_id].append(websocket)

    def disconnect(self, order_id: int, websocket: WebSocket):
        if websocket in self.active_connections[order_id]:
            self.active_connections[order_id].remove(websocket)
        if not self.active_connections[order_id]:
            self.active_connections.pop(order_id, None)

    async def broadcast(self, order_id: int, message: dict):
        stale_connections = []
        for connection in self.active_connections[order_id]:
            try:
                await connection.send_json(message)
            except Exception:
                stale_connections.append(connection)

        for connection in stale_connections:
            self.disconnect(order_id, connection)


manager = DeliveryConnectionManager()
