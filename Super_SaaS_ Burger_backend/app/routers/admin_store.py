from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
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

    return AdminStoreResponse(
        id=tenant.id,
        slug=tenant.slug,
        custom_domain=tenant.custom_domain,
        business_name=tenant.business_name,
        manual_open_status=tenant.manual_open_status,
    )
