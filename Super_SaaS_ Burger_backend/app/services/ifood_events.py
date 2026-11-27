from datetime import datetime
from uuid import UUID

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.ifood_event import IFoodEvent
from app.models.tenant import Tenant

IFOOD_API = "https://merchant-api.ifood.com.br"
EVENTS_URL = f"{IFOOD_API}/events/v1.0"


def poll_ifood_events(
    http: httpx.Client,
    db: Session,
    *,
    access_token: str,
    tenant_id: int,
    merchant_id: UUID,
) -> int:
    """Collect events for one authorized test merchant and acknowledge after commit."""
    if db.get(Tenant, tenant_id) is None:
        raise ValueError("Unknown pilot tenant")
    headers = {"Authorization": f"Bearer {access_token}"}
    response = http.get(
        f"{EVENTS_URL}/events:polling",
        headers={**headers, "x-polling-merchants": str(merchant_id)},
        params={"categories": "FOOD"},
    )
    response.raise_for_status()
    if response.status_code == 204:
        return 0
    events = response.json()
    if not isinstance(events, list):
        raise ValueError("Invalid iFood polling response")

    rows = {}
    for event in events:
        if UUID(event["merchantId"]) != merchant_id:
            continue
        event_id = str(UUID(event["id"]))
        code = event["fullCode"]
        if not isinstance(code, str) or not 0 < len(code) <= 64:
            raise ValueError("Invalid iFood event code")
        occurred_at = datetime.fromisoformat(event["createdAt"])
        if occurred_at.utcoffset() is None:
            raise ValueError("iFood event requires a timestamp with timezone")
        order_id = event.get("orderId")
        rows[event_id] = {
            "event_id": event_id,
            "tenant_id": tenant_id,
            "merchant_id": str(merchant_id),
            "order_id": str(UUID(order_id)) if order_id else None,
            "code": code,
            "occurred_at": occurred_at,
        }

    if not rows:
        return 0
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    stored = db.query(IFoodEvent.event_id, IFoodEvent.tenant_id, IFoodEvent.merchant_id)
    # Keep batches below SQLite's bound-parameter limit in local environments.
    ids = list(rows)
    for start in range(0, len(ids), 100):
        batch = ids[start : start + 100]
        db.execute(
            insert(IFoodEvent).values([rows[event_id] for event_id in batch])
            .on_conflict_do_nothing(index_elements=[IFoodEvent.event_id])
        )
        for _, existing_tenant_id, existing_merchant_id in stored.filter(IFoodEvent.event_id.in_(batch)):
            if existing_tenant_id != tenant_id or existing_merchant_id != str(merchant_id):
                raise ValueError("iFood event belongs to a different tenant connection")
    db.commit()
    http.post(
        f"{EVENTS_URL}/events/acknowledgment",
        headers=headers,
        json=[{"id": event_id} for event_id in ids],
    ).raise_for_status()
    return len(ids)
