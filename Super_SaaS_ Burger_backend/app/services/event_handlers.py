from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.order import Order
from app.services.customer_stats import update_customer_stats_for_order
from app.services.event_bus import event_bus
from app.services.whatsapp_outbound import send_whatsapp_message


def _with_session(handler):
    def wrapper(payload: dict) -> None:
        db: Session = SessionLocal()
        try:
            handler(db, payload)
        finally:
            db.close()

    return wrapper


@_with_session
def handle_order_created(db: Session, payload: dict) -> None:
    send_whatsapp_message(
        db,
        tenant_id=payload["tenant_id"],
        phone=payload["customer_phone"],
        template="order_confirmed",
        variables={
            "customer_name": payload.get("customer_name") or "Cliente",
            "order_number": payload["order_id"],
            "total_cents": payload.get("total_cents", 0),
            "estimated_time": payload.get("estimated_time", "30 min"),
        },
        order_id=payload["order_id"],
    )


@_with_session
def handle_order_status_changed(db: Session, payload: dict) -> None:
    status = payload.get("status")
    template = None
    if status in {"EM_PREPARO", "PREPARO"}:
        template = "order_in_preparation"
    elif status == "PRONTO":
        template = "order_ready"
    elif status in {"SAIU", "SAIU_PARA_ENTREGA"}:
        template = "order_out_for_delivery"
    elif status == "ENTREGUE":
        template = "order_delivered"

    if not template:
        return

    send_whatsapp_message(
        db,
        tenant_id=payload["tenant_id"],
        phone=payload["customer_phone"],
        template=template,
        variables={
            "customer_name": payload.get("customer_name") or "Cliente",
            "order_number": payload["order_id"],
            "total_cents": payload.get("total_cents", 0),
            "estimated_time": payload.get("estimated_time", "30 min"),
        },
        order_id=payload["order_id"],
    )


@_with_session
def handle_order_delivered(db: Session, payload: dict) -> None:
    order = (
        db.query(Order)
        .filter(
            Order.id == payload["order_id"],
            Order.tenant_id == payload["tenant_id"],
        )
        .first()
    )
    if not order:
        return
    update_customer_stats_for_order(db, order)
    db.commit()


event_bus.subscribe("order.created", handle_order_created)
event_bus.subscribe("order.status.changed", handle_order_status_changed)
event_bus.subscribe("order.delivered", handle_order_delivered)
