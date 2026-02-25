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
from app.models.tenant_public_settings import TenantPublicSettings

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


class PublicSettingsPayload(BaseModel):
    cover_image_url: str | None = None
    cover_video_url: str | None = None
    logo_url: str | None = None
    theme: str | None = None
    primary_color: str | None = None
    is_open: bool = True
    estimated_time_min: int | None = None
    banner_blur_enabled: bool = True
    banner_blur_intensity: int | None = None
    banner_overlay_opacity: float | None = None


class PublicSettingsResponse(PublicSettingsPayload):
    tenant_id: int


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


@router.get("", response_model=TenantResponse)
def get_current_tenant(
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado")

    return {
        "id": tenant.id,
        "slug": tenant.slug,
        "custom_domain": tenant.custom_domain,
        "business_name": tenant.business_name,
    }


@router.get("/public-settings", response_model=PublicSettingsResponse)
def get_public_settings(
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    settings = (
        db.query(TenantPublicSettings)
        .filter(TenantPublicSettings.tenant_id == user.tenant_id)
        .first()
    )
    if not settings:
        return PublicSettingsResponse(
            tenant_id=user.tenant_id,
            cover_image_url=None,
            cover_video_url=None,
            logo_url=None,
            theme=None,
            primary_color=None,
            is_open=True,
            estimated_time_min=None,
            banner_blur_enabled=True,
            banner_blur_intensity=6,
            banner_overlay_opacity=0.55,
        )
    return PublicSettingsResponse(
        tenant_id=settings.tenant_id,
        cover_image_url=settings.cover_image_url,
        cover_video_url=settings.cover_video_url,
        logo_url=settings.logo_url,
        theme=settings.theme,
        primary_color=settings.primary_color,
        is_open=settings.is_open,
        estimated_time_min=settings.estimated_time_min,
        banner_blur_enabled=settings.banner_blur_enabled,
        banner_blur_intensity=settings.banner_blur_intensity,
        banner_overlay_opacity=settings.banner_overlay_opacity,
    )


@router.patch("/public-settings", response_model=PublicSettingsResponse)
def update_public_settings(
    payload: PublicSettingsPayload,
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    settings = (
        db.query(TenantPublicSettings)
        .filter(TenantPublicSettings.tenant_id == user.tenant_id)
        .first()
    )
    if not settings:
        settings = TenantPublicSettings(tenant_id=user.tenant_id)
        db.add(settings)

    settings.cover_image_url = payload.cover_image_url
    settings.cover_video_url = payload.cover_video_url
    settings.logo_url = payload.logo_url
    settings.theme = payload.theme
    settings.primary_color = payload.primary_color
    settings.is_open = payload.is_open
    settings.estimated_time_min = payload.estimated_time_min
    settings.banner_blur_enabled = payload.banner_blur_enabled
    settings.banner_blur_intensity = payload.banner_blur_intensity
    settings.banner_overlay_opacity = payload.banner_overlay_opacity

    db.commit()
    db.refresh(settings)

    return PublicSettingsResponse(
        tenant_id=settings.tenant_id,
        cover_image_url=settings.cover_image_url,
        cover_video_url=settings.cover_video_url,
        logo_url=settings.logo_url,
        theme=settings.theme,
        primary_color=settings.primary_color,
        is_open=settings.is_open,
        estimated_time_min=settings.estimated_time_min,
        banner_blur_enabled=settings.banner_blur_enabled,
        banner_blur_intensity=settings.banner_blur_intensity,
        banner_overlay_opacity=settings.banner_overlay_opacity,
    )
