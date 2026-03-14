from __future__ import annotations

from app.models.order import Order
from app.services.event_bus import event_bus


def _normalize_status(status: str | None) -> str:
    return (status or "").strip().upper()


def _resolve_order_number(order: Order) -> int:
    return int(order.daily_order_number or order.id)


def _resolve_total_cents(order: Order) -> int:
    total_value = order.total_cents
    if total_value is None:
        total_value = order.valor_total
    return int(total_value or 0)


def build_order_payload(order: Order, previous_status: str | None = None) -> dict:
    return {
        "order_id": order.id,
        "order_number": _resolve_order_number(order),
        "daily_order_number": order.daily_order_number,
        "tenant_id": order.tenant_id,
        "status": _normalize_status(order.status),
        "previous_status": _normalize_status(previous_status) if previous_status else None,
        "customer_name": order.cliente_nome,
        "customer_phone": order.cliente_telefone,
        "total_cents": _resolve_total_cents(order),
        "estimated_time": "30 min",
        "delivery_type": order.tipo_entrega,
        "assigned_delivery_user_id": order.assigned_delivery_user_id,
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
