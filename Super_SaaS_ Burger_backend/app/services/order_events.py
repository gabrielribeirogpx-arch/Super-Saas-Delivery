from __future__ import annotations

from app.models.order import Order
from app.services.event_bus import event_bus


def _normalize_status(status: str | None) -> str:
    return (status or "").strip().upper()


def build_order_payload(order: Order, previous_status: str | None = None) -> dict:
    return {
        "order_id": order.id,
        "tenant_id": order.tenant_id,
        "status": _normalize_status(order.status),
        "previous_status": _normalize_status(previous_status) if previous_status else None,
        "customer_name": order.cliente_nome,
        "customer_phone": order.cliente_telefone,
        "total_cents": int(order.total_cents or order.valor_total or 0),
        "estimated_time": "30 min",
        "delivery_type": order.tipo_entrega,
    }


def emit_order_created(order: Order) -> None:
    event_bus.emit("order.created", build_order_payload(order))


def emit_order_status_changed(order: Order, previous_status: str | None) -> None:
    if previous_status and _normalize_status(previous_status) == _normalize_status(order.status):
        return
    payload = build_order_payload(order, previous_status=previous_status)
    event_bus.emit("order.status.changed", payload)
    status = payload["status"]
    if status == "PRONTO":
        event_bus.emit("order.ready", payload)
    if status == "ENTREGUE":
        event_bus.emit("order.delivered", payload)
