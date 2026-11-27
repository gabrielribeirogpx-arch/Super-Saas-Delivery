from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.ifood_event import IFoodEvent
from app.models.tenant import Tenant

router = APIRouter(prefix="/api/admin/store", tags=["admin-store"])


class AdminStoreStatusPatch(BaseModel):
    manual_open_status: bool


class AdminStoreResponse(BaseModel):
    id: int
    slug: str
    custom_domain: str | None
    business_name: str
    manual_open_status: bool
    estimated_prep_time: str | None
    delivery_fee: float


class AdminStorePatch(BaseModel):
    manual_open_status: bool | None = None
    estimated_prep_time: str | None = Field(default=None, max_length=50)
    delivery_fee: float | None = Field(default=None, ge=0)


def _serialize_tenant(tenant: Tenant) -> AdminStoreResponse:
    return AdminStoreResponse(
        id=tenant.id,
        slug=tenant.slug,
        custom_domain=tenant.custom_domain,
        business_name=tenant.business_name,
        manual_open_status=tenant.manual_open_status,
        estimated_prep_time=tenant.estimated_prep_time,
        delivery_fee=float(tenant.delivery_fee or 0),
    )


@router.get("", response_model=AdminStoreResponse)
def get_store(
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado")
    return _serialize_tenant(tenant)


@router.patch("", response_model=AdminStoreResponse)
def update_store(
    payload: AdminStorePatch,
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado")

    if payload.manual_open_status is not None:
        tenant.manual_open_status = payload.manual_open_status

    if payload.estimated_prep_time is not None:
        normalized_prep_time = payload.estimated_prep_time.strip()
        tenant.estimated_prep_time = normalized_prep_time or None

    if payload.delivery_fee is not None:
        tenant.delivery_fee = payload.delivery_fee

    db.commit()
    db.refresh(tenant)

    return _serialize_tenant(tenant)


@router.patch("/status", response_model=AdminStoreResponse)
def update_store_status(
    payload: AdminStoreStatusPatch,
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado")

    tenant.manual_open_status = payload.manual_open_status
    db.commit()
    db.refresh(tenant)

    return _serialize_tenant(tenant)


class IFoodEventSummary(BaseModel):
    code: str
    received_at: datetime


class IFoodIntegrationStatus(BaseModel):
    last_event: IFoodEventSummary | None


@router.get("/integrations/ifood", response_model=IFoodIntegrationStatus)
def get_ifood_integration(
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    event = (
        db.query(IFoodEvent.code, IFoodEvent.received_at)
        .filter(IFoodEvent.tenant_id == user.tenant_id)
        .order_by(IFoodEvent.received_at.desc(), IFoodEvent.event_id.desc())
        .first()
    )
    if event is None:
        return IFoodIntegrationStatus(last_event=None)

    # SQLite returns timestamps without an offset, including UTC server defaults.
    received_at = event.received_at
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    return IFoodIntegrationStatus(
        last_event=IFoodEventSummary(code=event.code, received_at=received_at),
    )
