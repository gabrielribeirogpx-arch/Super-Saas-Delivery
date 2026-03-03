from __future__ import annotations

from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.delivery_log import DeliveryLog
from app.services.admin_audit import log_admin_action
from app.services.passwords import hash_password

router = APIRouter(prefix="/api/admin", tags=["admin-users"])


class DeliveryUserCreate(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)


class DeliveryUserRead(BaseModel):
    id: int
    tenant_id: int
    email: EmailStr
    name: str
    role: str
    active: bool


class DeliveryUserStatsRead(BaseModel):
    total_deliveries: int
    today_deliveries: int
    avg_time_minutes: float
    completion_rate: float


class DeliveryUserLocationRead(BaseModel):
    delivery_user_id: int
    lat: float
    lng: float
    updated_at: datetime


@router.post(
    "/{tenant_id}/delivery-users",
    response_model=DeliveryUserRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_delivery_user(
    tenant_id: int,
    payload: DeliveryUserCreate,
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    if int(user.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant não autorizado")

    normalized_email = payload.email.strip().lower()
    existing = (
        db.query(AdminUser)
        .filter(AdminUser.tenant_id == tenant_id, AdminUser.email == normalized_email)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email já cadastrado")

    delivery_user = AdminUser(
        tenant_id=tenant_id,
        email=normalized_email,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        role="DELIVERY",
        active=True,
    )
    db.add(delivery_user)
    db.flush()

    log_admin_action(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action="create_user",
        entity_type="admin_user",
        entity_id=delivery_user.id,
        meta={"email": delivery_user.email, "role": delivery_user.role},
    )
    db.commit()

    return {
        "id": delivery_user.id,
        "tenant_id": delivery_user.tenant_id,
        "email": delivery_user.email,
        "name": delivery_user.name,
        "role": delivery_user.role,
        "active": delivery_user.active,
    }


@router.get(
    "/{tenant_id}/delivery-users/locations",
    response_model=list[DeliveryUserLocationRead],
    include_in_schema=False,
)
def list_delivery_user_latest_locations(
    tenant_id: int,
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    if int(user.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant não autorizado")

    latest_location_per_user = (
        db.query(
            DeliveryLog.delivery_user_id.label("delivery_user_id"),
            func.max(DeliveryLog.id).label("latest_log_id"),
        )
        .filter(
            DeliveryLog.tenant_id == tenant_id,
            DeliveryLog.event_type == "location_update",
        )
        .group_by(DeliveryLog.delivery_user_id)
        .subquery()
    )

    rows = (
        db.query(
            DeliveryLog.delivery_user_id,
            DeliveryLog.latitude,
            DeliveryLog.longitude,
            DeliveryLog.created_at,
        )
        .join(latest_location_per_user, DeliveryLog.id == latest_location_per_user.c.latest_log_id)
        .order_by(DeliveryLog.delivery_user_id.asc())
        .all()
    )

    return [
        {
            "delivery_user_id": int(row.delivery_user_id),
            "lat": float(row.latitude),
            "lng": float(row.longitude),
            "updated_at": row.created_at,
        }
        for row in rows
        if row.latitude is not None and row.longitude is not None
    ]


@router.get(
    "/{tenant_id}/delivery-users/{delivery_user_id}/stats",
    response_model=DeliveryUserStatsRead,
    include_in_schema=False,
)
def get_delivery_user_stats(
    tenant_id: int,
    delivery_user_id: int,
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    if int(user.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant não autorizado")

    target_user = (
        db.query(AdminUser)
        .filter(AdminUser.id == delivery_user_id, AdminUser.tenant_id == tenant_id)
        .first()
    )
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário de entrega não encontrado")

    now_utc = datetime.now(timezone.utc)
    today_start_utc = datetime.combine(now_utc.date(), time.min, tzinfo=timezone.utc)

    totals_row = (
        db.query(
            func.count(
                case((DeliveryLog.event_type == "completed", 1))
            ).label("completed_count"),
            func.count(case((DeliveryLog.event_type == "started", 1))).label("started_count"),
            func.count(
                case(
                    (
                        and_(
                            DeliveryLog.event_type == "completed",
                            DeliveryLog.created_at >= today_start_utc,
                        ),
                        1,
                    )
                )
            ).label("today_completed_count"),
        )
        .filter(
            DeliveryLog.tenant_id == tenant_id,
            DeliveryLog.delivery_user_id == delivery_user_id,
            DeliveryLog.event_type.in_(["started", "completed"]),
        )
        .one()
    )

    per_order_events = (
        db.query(
            DeliveryLog.order_id.label("order_id"),
            func.min(case((DeliveryLog.event_type == "started", DeliveryLog.created_at))).label("started_at"),
            func.min(case((DeliveryLog.event_type == "completed", DeliveryLog.created_at))).label("completed_at"),
        )
        .filter(
            DeliveryLog.tenant_id == tenant_id,
            DeliveryLog.delivery_user_id == delivery_user_id,
            DeliveryLog.event_type.in_(["started", "completed"]),
        )
        .group_by(DeliveryLog.order_id)
        .all()
    )

    durations_minutes = [
        (event.completed_at - event.started_at).total_seconds() / 60.0
        for event in per_order_events
        if event.started_at is not None and event.completed_at is not None and event.completed_at >= event.started_at
    ]
    avg_time_minutes = (sum(durations_minutes) / len(durations_minutes)) if durations_minutes else 0.0

    started_count = int(totals_row.started_count or 0)
    completed_count = int(totals_row.completed_count or 0)
    completion_rate = (completed_count / started_count) if started_count > 0 else 0.0

    return {
        "total_deliveries": completed_count,
        "today_deliveries": int(totals_row.today_completed_count or 0),
        "avg_time_minutes": float(avg_time_minutes),
        "completion_rate": float(completion_rate),
    }
