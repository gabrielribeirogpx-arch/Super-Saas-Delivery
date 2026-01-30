from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import DEV_BOOTSTRAP_ALLOW, IS_DEV
from app.core.database import get_db, engine
from app.services.admin_bootstrap import ensure_admin_users_table, upsert_admin_user

router = APIRouter(prefix="/api/admin/bootstrap", tags=["admin-bootstrap"])


class AdminBootstrapPayload(BaseModel):
    tenant_id: int = Field(..., ge=1)
    email: EmailStr
    password: str | None = Field(None, min_length=1)
    name: str = Field(..., min_length=1)
    role: str = Field("admin", min_length=1)


class AdminBootstrapResponse(BaseModel):
    status: str
    created: bool
    tenant_id: int
    email: EmailStr
    name: str
    role: str
    active: bool


def _ensure_bootstrap_allowed() -> None:
    if not IS_DEV or not DEV_BOOTSTRAP_ALLOW:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.post("", response_model=AdminBootstrapResponse)
def bootstrap_admin(
    payload: AdminBootstrapPayload,
    db: Session = Depends(get_db),
):
    _ensure_bootstrap_allowed()
    try:
        ensure_admin_users_table(engine)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        admin, created = upsert_admin_user(
            db,
            tenant_id=payload.tenant_id,
            email=payload.email,
            name=payload.name,
            role=payload.role,
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AdminBootstrapResponse(
        status="created" if created else "updated",
        created=created,
        tenant_id=admin.tenant_id,
        email=admin.email,
        name=admin.name,
        role=admin.role,
        active=admin.active,
    )
