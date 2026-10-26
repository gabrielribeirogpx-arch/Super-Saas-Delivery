from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

from app.core.config import PUBLIC_BASE_DOMAIN
from app.core.domains import normalize_domain
from app.models.order import Order
from app.services.event_bus import event_bus


OUT_FOR_DELIVERY_STATUSES = {"OUT_FOR_DELIVERY", "SAIU", "SAIU_PARA_ENTREGA"}


def _normalize_status(status: str | None) -> str:
    return (status or "").strip().upper()


def _resolve_order_number(order: Order) -> int:
    return int(order.daily_order_number or order.id)


def _resolve_total_cents(order: Order) -> int:
    total_value = order.total_cents
    if total_value is None:
        total_value = order.valor_total
    return int(total_value or 0)


def _build_tracking_url(order: Order) -> str | None:
    token = str(getattr(order, "tracking_token", "") or "").strip()
    if not token or getattr(order, "tracking_revoked", False):
        return None

    expires_at = getattr(order, "tracking_expires_at", None)
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            return None

    public_domain = normalize_domain(PUBLIC_BASE_DOMAIN)
    if not public_domain:
        return None
    return f"https://{public_domain}/pedido/{quote(token, safe='')}"


def build_order_payload(order: Order, previous_status: str | None = None) -> dict:
    payload = {
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
    if payload["status"] in OUT_FOR_DELIVERY_STATUSES:
        tracking_url = _build_tracking_url(order)
        if tracking_url:
            payload["tracking_url"] = tracking_url
    return payload


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
