from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.services.admin_audit import log_admin_action
from app.services.passwords import hash_password

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])

ALLOWED_ROLES = {"admin", "operator", "cashier"}


class AdminUserRead(BaseModel):
    id: int
    tenant_id: int
    email: EmailStr
    name: str
    role: str
    active: bool


class AdminUserCreate(BaseModel):
    tenant_id: int = Field(..., ge=1)
    email: EmailStr
    name: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)


class AdminUserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    role: Optional[str] = Field(None, min_length=1)
    active: Optional[bool] = None


class AdminUserResetPassword(BaseModel):
    new_password: str = Field(..., min_length=6)


@router.get("", response_model=List[AdminUserRead])
def list_admin_users(
    tenant_id: int,
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    if int(user.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant não autorizado")

    users = (
        db.query(AdminUser)
        .filter(AdminUser.tenant_id == tenant_id)
        .order_by(AdminUser.id.asc())
        .all()
    )
    return [
        {
            "id": entry.id,
            "tenant_id": entry.tenant_id,
            "email": entry.email,
            "name": entry.name,
            "role": entry.role,
            "active": entry.active,
        }
        for entry in users
    ]


@router.post("", response_model=AdminUserRead, status_code=status.HTTP_201_CREATED)
def create_admin_user(
    payload: AdminUserCreate,
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    if int(user.tenant_id) != int(payload.tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant não autorizado")

    role = payload.role.strip().lower()
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role inválida")

    email = payload.email.strip().lower()
    existing = (
        db.query(AdminUser)
        .filter(AdminUser.tenant_id == payload.tenant_id, AdminUser.email == email)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email já cadastrado")

    admin = AdminUser(
        tenant_id=payload.tenant_id,
        email=email,
        name=payload.name.strip(),
        role=role,
        password_hash=hash_password(payload.password),
        active=True,
    )
    db.add(admin)
    db.flush()

    log_admin_action(
        db,
        tenant_id=admin.tenant_id,
        user_id=user.id,
        action="create_user",
        entity_type="admin_user",
        entity_id=admin.id,
        meta={"email": admin.email, "role": admin.role},
    )
    db.commit()

    return {
        "id": admin.id,
        "tenant_id": admin.tenant_id,
        "email": admin.email,
        "name": admin.name,
        "role": admin.role,
        "active": admin.active,
    }


@router.put("/{user_id}", response_model=AdminUserRead)
def update_admin_user(
    user_id: int,
    payload: AdminUserUpdate,
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    target = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not target or int(target.tenant_id) != int(user.tenant_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    if payload.role is not None:
        role = payload.role.strip().lower()
        if role not in ALLOWED_ROLES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role inválida")
        target.role = role

    if payload.name is not None:
        target.name = payload.name.strip()

    active_changed = False
    if payload.active is not None:
        if not payload.active and target.id == user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não é possível desativar o próprio usuário logado",
            )
        if target.active != payload.active:
            active_changed = True
        target.active = payload.active

    log_admin_action(
        db,
        tenant_id=target.tenant_id,
        user_id=user.id,
        action="update_user",
        entity_type="admin_user",
        entity_id=target.id,
        meta={"role": target.role, "active": target.active},
    )

    if active_changed:
        log_admin_action(
            db,
            tenant_id=target.tenant_id,
            user_id=user.id,
            action="deactivate_user" if not target.active else "activate_user",
            entity_type="admin_user",
            entity_id=target.id,
        )

    db.commit()

    return {
        "id": target.id,
        "tenant_id": target.tenant_id,
        "email": target.email,
        "name": target.name,
        "role": target.role,
        "active": target.active,
    }


@router.post("/{user_id}/reset_password")
def reset_admin_password(
    user_id: int,
    payload: AdminUserResetPassword,
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    target = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not target or int(target.tenant_id) != int(user.tenant_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    target.password_hash = hash_password(payload.new_password)
    log_admin_action(
        db,
        tenant_id=target.tenant_id,
        user_id=user.id,
        action="reset_password",
        entity_type="admin_user",
        entity_id=target.id,
    )
    db.commit()
    return {"ok": True}
