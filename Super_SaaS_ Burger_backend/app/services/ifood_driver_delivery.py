from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.admin_user import AdminUser
from app.models.ifood_driver_delivery import IFoodDriverDelivery
from app.models.ifood_order import IFoodOrder
from app.routers.admin_ifood_orders import _order_access, send_ifood_dispatch
from app.services.ifood_orders import latest_order_state

AVAILABLE = "READY_FOR_DELIVERY"
ASSIGNED = "DRIVER_ASSIGNED"
IN_ROUTE = "OUT_FOR_DELIVERY"
COMPLETE = "DELIVERED"
CLOSED_ORDER_STATES = {"CANCELLED", "CONCLUDED", "DELIVERED"}


def _query(tenant_id: int, merchant_id: str):
    return select(IFoodDriverDelivery, IFoodOrder, latest_order_state().label("state")).join(
        IFoodOrder, IFoodOrder.order_id == IFoodDriverDelivery.order_id,
    ).where(IFoodOrder.tenant_id == tenant_id, IFoodOrder.merchant_id == merchant_id)


def _workflow(delivery: IFoodDriverDelivery, order: IFoodOrder, state: str | None) -> str | None:
    if delivery.completed_at or state in {"CONCLUDED", "DELIVERED"}:
        return COMPLETE
    if state in CLOSED_ORDER_STATES:
        return None
    if delivery.started_at:
        return IN_ROUTE
    if delivery.assigned_driver_id and state in {"READY_TO_PICKUP", "DISPATCHED"}:
        return ASSIGNED
    if state == "READY_TO_PICKUP" and not order.dispatch_requested_at:
        return AVAILABLE
    return None


def _serialize(delivery: IFoodDriverDelivery, order: IFoodOrder, workflow: str) -> dict:
    destination = delivery.destination
    display_id = str(order.details["display_id"])
    payment = order.details.get("payment") or []
    methods = list(dict.fromkeys(
        entry["method"] for entry in payment if entry.get("method") and entry.get("type") != "ONLINE"
    ))
    return {
        "id": -delivery.id, "display_id": display_id, "source": "ifood",
        "daily_order_number": int(display_id) if display_id.isdecimal() else delivery.id,
        "status": workflow, "raw_status": workflow, "customer_name": destination.get("name") or "Cliente iFood",
        "address": destination["address"], "neighborhood": destination.get("neighborhood"),
        "complement": destination.get("complement"), "reference": destination.get("reference"),
        "notes": destination.get("notes"), "order_type": "delivery",
        "payment_method": " / ".join(methods) if methods else "Pago no iFood" if payment else "",
        "total_cents": int(Decimal(str(order.details.get("total", 0))) * 100),
        "destination_lat": destination.get("latitude"), "destination_lng": destination.get("longitude"),
        "created_at": order.created_at.isoformat(),
    }


def driver_ifood_state(db: Session, driver: AdminUser) -> tuple[list[dict], list[dict], int]:
    access = _order_access(db, driver.tenant_id)
    if access is None or not access[1]:
        return [], [], 0
    _, merchant_id, _ = access
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    base = _query(driver.tenant_id, merchant_id)
    state = base.selected_columns.state
    jobs = db.execute(base.where(
        IFoodDriverDelivery.completed_at.is_(None),
        (IFoodDriverDelivery.assigned_driver_id == driver.id)
        | (IFoodDriverDelivery.assigned_driver_id.is_(None) & (state == "READY_TO_PICKUP")),
    ).order_by(IFoodOrder.created_at, IFoodDriverDelivery.id)).all()
    available, assigned = [], []
    for delivery, order, state in jobs:
        workflow = _workflow(delivery, order, state)
        if workflow == AVAILABLE:
            available.append(_serialize(delivery, order, workflow))
        elif workflow in {ASSIGNED, IN_ROUTE}:
            assigned.append(_serialize(delivery, order, workflow))

    completed = db.scalar(select(func.count()).select_from(
        base.where(
            IFoodDriverDelivery.assigned_driver_id == driver.id,
            IFoodDriverDelivery.completed_at >= today,
        ).subquery(),
    ))
    return available, assigned, int(completed or 0)


def _load(db: Session, driver: AdminUser, delivery_id: int, *, lock: bool = False):
    access = _order_access(db, driver.tenant_id)
    if access is None or not access[1]:
        raise HTTPException(404, "Entrega não encontrada.")
    token, merchant_id, _ = access
    query = _query(driver.tenant_id, merchant_id).where(IFoodDriverDelivery.id == -delivery_id)
    row = db.execute(query.with_for_update() if lock else query).one_or_none()
    if row is None:
        raise HTTPException(404, "Entrega não encontrada.")
    delivery, order, state = row
    workflow = _workflow(delivery, order, state)
    if workflow is None or (workflow != AVAILABLE and delivery.assigned_driver_id != driver.id):
        raise HTTPException(404, "Entrega não encontrada.")
    return delivery, order, state, workflow, token


def get_driver_ifood_delivery(db: Session, driver: AdminUser, delivery_id: int) -> dict:
    delivery, order, _, workflow, _ = _load(db, driver, delivery_id)
    return _serialize(delivery, order, workflow)


def act_on_ifood_delivery(db: Session, driver: AdminUser, delivery_id: int, action: str) -> dict:
    delivery, order, state, workflow, token = _load(db, driver, delivery_id, lock=True)
    now = datetime.now(timezone.utc)
    if action == "accept" and workflow == AVAILABLE:
        delivery.assigned_driver_id = driver.id
        workflow = ASSIGNED
    elif action == "start" and workflow == ASSIGNED:
        if not token:
            raise HTTPException(503, "A conexão com o iFood está indisponível.")
        send_ifood_dispatch(db, order, state, token)
        delivery.started_at = now
        workflow = IN_ROUTE
    elif action == "complete" and workflow == IN_ROUTE:
        delivery.completed_at = now
        workflow = COMPLETE
    elif not (
        (action == "accept" and delivery.assigned_driver_id == driver.id)
        or (action == "start" and workflow == IN_ROUTE)
        or (action == "complete" and workflow == COMPLETE and delivery.assigned_driver_id == driver.id)
    ):
        raise HTTPException(409, "A entrega não permite esta ação.")
    db.commit()
    return {"ok": True, "status": workflow, "order_id": delivery_id}


def record_ifood_driver_location(db: Session, driver: AdminUser, delivery_id: int, lat: float, lng: float) -> dict:
    delivery, _, _, workflow, _ = _load(db, driver, delivery_id, lock=True)
    if workflow != IN_ROUTE:
        raise HTTPException(409, "A entrega precisa estar em andamento.")
    delivery.last_location = {"latitude": lat, "longitude": lng, "recorded_at": datetime.now(timezone.utc).isoformat()}
    db.commit()
    return {"success": True, "order_id": delivery_id}
