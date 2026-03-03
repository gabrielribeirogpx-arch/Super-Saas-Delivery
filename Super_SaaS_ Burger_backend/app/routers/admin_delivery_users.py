from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
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
