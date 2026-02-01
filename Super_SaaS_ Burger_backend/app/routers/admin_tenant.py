from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.tenant import Tenant

router = APIRouter(prefix="/api/admin/tenant", tags=["admin-tenant"])

SLUG_PATTERN = re.compile(r"^[a-z0-9-]{3,}$")


class TenantUpdate(BaseModel):
    slug: str = Field(..., min_length=3)
    custom_domain: str | None = None


class TenantResponse(BaseModel):
    id: int
    slug: str
    custom_domain: str | None
    business_name: str


@router.patch("", response_model=TenantResponse)
def update_current_tenant(
    payload: TenantUpdate,
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    slug = payload.slug.strip().lower()
    if not SLUG_PATTERN.match(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slug inválido. Use letras minúsculas, números e hífen (mínimo 3).",
        )

    custom_domain = payload.custom_domain.strip().lower() if payload.custom_domain else None
    if custom_domain == "":
        custom_domain = None

    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado")

    existing_slug = (
        db.query(Tenant)
        .filter(Tenant.slug == slug, Tenant.id != tenant.id)
        .first()
    )
    if existing_slug:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Slug já em uso")

    if custom_domain:
        existing_domain = (
            db.query(Tenant)
            .filter(func.lower(Tenant.custom_domain) == custom_domain, Tenant.id != tenant.id)
            .first()
        )
        if existing_domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Domínio personalizado já em uso",
            )

    tenant.slug = slug
    tenant.custom_domain = custom_domain
    db.commit()
    db.refresh(tenant)

    return {
        "id": tenant.id,
        "slug": tenant.slug,
        "custom_domain": tenant.custom_domain,
        "business_name": tenant.business_name,
    }
