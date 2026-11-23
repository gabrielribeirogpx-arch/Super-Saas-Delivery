"""Enqueue before commit. Payloads contain lifecycle metadata, never buyer PII."""
from uuid import uuid4
from app.models.order_durability import OrderOutbox
from app.services.order_statuses import canonical_status


def _enqueue(db, order, effects, previous=None):
    event = uuid4().hex
    payload = {"status": canonical_status(order.status), "previous_status": canonical_status(previous),
               "assigned_delivery_user_id": getattr(order, "assigned_delivery_user_id", None)}
    for effect, stream in effects:
        db.add(OrderOutbox(tenant_id=order.tenant_id, order_id=order.id,
            event_key=event, effect=effect, stream=stream, payload=payload))


def enqueue_order_created(db, order):
    _enqueue(db, order, [("whatsapp.created", "whatsapp")])


def enqueue_order_status_changed(db, order, previous):
    current = canonical_status(order.status)
    if previous and current == canonical_status(previous):
        return
    effects = []
    if current in {"EM_PREPARO", "PRONTO", "SAIU_PARA_ENTREGA", "ENTREGUE"}:
        effects.append(("whatsapp.status", "whatsapp"))
    if current == "ENTREGUE":
        effects.append(("customer.delivered", "stats"))
    if getattr(order, "assigned_delivery_user_id", None) is not None:
        effects.append(("delivery.status", "delivery"))
    _enqueue(db, order, effects, previous)


def enqueue_wazza_order_mutation(db, order, mutation):
    db.add(OrderOutbox(
        tenant_id=order.tenant_id, order_id=order.id, event_key=uuid4().hex,
        effect=f"whatsapp.wazza_{mutation.action}", stream="whatsapp",
        payload={"status": canonical_status(order.status), "mutation_id": mutation.id,
                 "total_cents": order.total_cents},
    ))
