import logging
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.ifood_event import IFoodEvent
from app.models.ifood_order import IFoodOrder
from app.services.ifood_events import IFOOD_API

ORDERS_URL = f"{IFOOD_API}/order/v1.0/orders"
CONFIRMATION_WINDOW = timedelta(minutes=8)
ORDER_STATES = {
    "PLACED", "CONFIRMED", "PREPARATION_STARTED", "READY_TO_PICKUP",
    "DISPATCHED", "DELIVERED", "CONCLUDED", "CANCELLED",
}
logger = logging.getLogger(__name__)


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def pilot_credentials() -> tuple[str, int, UUID]:
    if os.getenv("IFOOD_PILOT_ENABLED") != "true":
        raise ValueError("set IFOOD_PILOT_ENABLED=true")
    try:
        token = os.environ["IFOOD_PILOT_ACCESS_TOKEN"].strip()
        tenant_id = int(os.environ["IFOOD_PILOT_TENANT_ID"])
        merchant_id = UUID(os.environ["IFOOD_PILOT_MERCHANT_ID"])
        if token and tenant_id > 0:
            return token, tenant_id, merchant_id
    except (KeyError, ValueError):
        pass
    raise ValueError("configure valid pilot token, merchant UUID and tenant ID")


def item_summary(item: dict, depth: int = 0) -> dict:
    return {
        "name": item["name"],
        "quantity": item["quantity"],
        "observations": item.get("observations"),
        "options": [item_summary(option, depth + 1) for option in item.get("options", [])]
        if depth < 3 else [],
    }


def order_summary(payload: dict) -> dict:
    return {
        "display_id": payload["displayId"],
        "order_type": payload["orderType"],
        "timing": payload.get("orderTiming"),
        "delivered_by": (payload.get("delivery") or {}).get("deliveredBy"),
        "scheduled_for": (payload.get("schedule") or {}).get("deliveryDateTimeStart"),
        "total": payload["total"]["orderAmount"],
        "payment": [
            {"method": method.get("method"), "type": method.get("type")}
            for method in (payload.get("payments") or {}).get("methods", [])
        ],
        "items": [item_summary(item) for item in payload["items"]],
        "observations": payload.get("extraInfo"),
    }


def import_pilot_orders(http: httpx.Client, db: Session, token: str, tenant_id: int, merchant_id: UUID) -> int:
    """Hydrate the durable inbox after polling so a temporary 404 can be retried."""
    merchant = str(merchant_id)
    pending = db.scalars(
        select(IFoodEvent.order_id)
        .where(
            IFoodEvent.tenant_id == tenant_id,
            IFoodEvent.merchant_id == merchant,
            IFoodEvent.code == "PLACED",
            IFoodEvent.order_id.is_not(None),
            IFoodEvent.occurred_at >= datetime.now(timezone.utc) - timedelta(minutes=10),
            ~select(IFoodOrder.order_id).where(
                IFoodOrder.order_id == IFoodEvent.order_id,
            ).exists(),
        )
        .distinct().order_by(IFoodEvent.order_id).limit(20)
    ).all()
    db.rollback()
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    count = 0
    for order_id in pending:
        response = http.get(f"{ORDERS_URL}/{order_id}", headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 404:
            continue
        response.raise_for_status()
        try:
            payload = response.json()
            if (
                str(UUID(payload["id"])) != order_id
                or str(UUID(payload["merchant"]["id"])) != merchant
                or payload["category"] != "FOOD"
                or payload.get("isTest") is not True
            ):
                logger.warning("Skipped iFood order outside the test store scope")
                continue
            created_at = datetime.fromisoformat(payload["createdAt"])
            if created_at.utcoffset() is None:
                raise ValueError("missing order timezone")
            details = order_summary(payload)
        except (AttributeError, KeyError, TypeError, ValueError):
            logger.warning("Invalid iFood order details")
            continue
        result = db.execute(insert(IFoodOrder).values(
            order_id=order_id, tenant_id=tenant_id, merchant_id=merchant,
            created_at=created_at, details=details,
        ).on_conflict_do_nothing(index_elements=[IFoodOrder.order_id]))
        db.commit()
        count += result.rowcount
    return count


def latest_order_state():
    return (
        select(IFoodEvent.code)
        .where(
            IFoodEvent.tenant_id == IFoodOrder.tenant_id,
            IFoodEvent.merchant_id == IFoodOrder.merchant_id,
            IFoodEvent.order_id == IFoodOrder.order_id,
            IFoodEvent.code.in_(ORDER_STATES),
        )
        .order_by(IFoodEvent.occurred_at.desc(), (IFoodEvent.code == "PLACED").asc(), IFoodEvent.event_id.desc())
        .limit(1)
        .correlate(IFoodOrder)
        .scalar_subquery()
    )
