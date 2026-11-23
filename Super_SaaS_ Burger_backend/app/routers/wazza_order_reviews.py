"""Restaurant review queue for customer-initiated Wazza order changes."""

from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import func, or_

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core import config
from app.core.database import get_db
from app.deps import get_request_tenant_id, require_admin_tenant_access, require_role
from app.models.wazza_mcp import WazzaMcpCredential, WazzaOrderMutation
from app.services.wazza_order_mutations import decide, queue_item

router = APIRouter(prefix="/api/orders/wazza/requests", tags=["wazza-order-reviews"])
require_operator = require_role(["owner", "admin", "operator"])


class DecisionArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    action: Literal["approve", "reject", "verify"]
    reason: str = Field(min_length=5, max_length=300)


@router.get("")
def list_reviews(
    request: Request,
    before: int | None = Query(default=None, gt=0),
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    user=Depends(require_operator),
):
    require_admin_tenant_access(request=request, tenant_id=tenant_id, user=user)
    query = db.query(WazzaOrderMutation).filter_by(tenant_id=tenant_id)
    if before is not None:
        query = query.filter(WazzaOrderMutation.id < before)
    rows = query.order_by(WazzaOrderMutation.id.desc()).limit(51).all()
    return {"items": [queue_item(row) for row in rows[:50]], "next": rows[49].id if len(rows) > 50 else None}


@router.post("/{request_id}/decision")
def review(
    request: Request,
    request_id: int,
    arguments: DecisionArguments,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    user=Depends(require_operator),
):
    require_admin_tenant_access(request=request, tenant_id=tenant_id, user=user)
    result = decide(db, tenant_id, user.id, request_id, arguments.action, arguments.reason)
    db.commit()
    return result

@router.get("/connection")
def connection_status(
    request: Request,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    user=Depends(require_operator),
):
    require_admin_tenant_access(request=request, tenant_id=tenant_id, user=user)
    active, last_contact = db.query(
        func.count(WazzaMcpCredential.id), func.max(WazzaMcpCredential.last_used_at),
    ).filter(
        WazzaMcpCredential.tenant_id == tenant_id,
        WazzaMcpCredential.revoked_at.is_(None),
        or_(WazzaMcpCredential.expires_at.is_(None),
            WazzaMcpCredential.expires_at > datetime.now(timezone.utc)),
    ).one()
    if last_contact is not None and last_contact.tzinfo is None:
        last_contact = last_contact.replace(tzinfo=timezone.utc)
    if not config.WAZZA_MCP_ENABLED:
        state = "disabled"
    elif not active:
        state = "setup_required"
    elif last_contact is None:
        state = "awaiting_contact"
    else:
        state = "contact_verified"
    return {"state": state, "last_contact": last_contact}
