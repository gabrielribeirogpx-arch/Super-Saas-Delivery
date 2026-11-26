from __future__ import annotations

import re
from io import BytesIO
from types import SimpleNamespace
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.tenant import Tenant
from app.services.plan_access import require_feature
from app.services.printing import TicketPaperWidth, render_ticket_pdf
from app.models.tenant_public_settings import TenantPublicSettings
from app.services.appearance_service import appearance_service

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
    manual_open_status: bool


class PublicSettingsPayload(BaseModel):
    cover_image_url: str | None = None
    cover_video_url: str | None = None
    logo_url: str | None = None
    theme: str | None = None
    primary_color: str | None = None


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
        require_feature(db, user.tenant_id, "custom_domain")
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
        "manual_open_status": tenant.manual_open_status,
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
        "manual_open_status": tenant.manual_open_status,
    }


class TicketPrintingSettings(BaseModel):
    paper_width_mm: TicketPaperWidth


@router.get("/printing", response_model=TicketPrintingSettings)
def get_ticket_printing_settings(
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(404, "Loja não encontrada")
    return TicketPrintingSettings(paper_width_mm=tenant.ticket_paper_width_mm)


@router.put("/printing", response_model=TicketPrintingSettings)
def update_ticket_printing_settings(
    settings: TicketPrintingSettings,
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(404, "Loja não encontrada")
    tenant.ticket_paper_width_mm = settings.paper_width_mm
    db.commit()
    return settings


@router.get(
    "/printing/test",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}}},
)
def test_ticket_printing(
    paper_width_mm: Literal["58", "80"],
    _user: AdminUser = Depends(require_role(["admin", "owner"])),
):
    sample = SimpleNamespace(
        id=1,
        cliente_nome="Cliente de exemplo",
        tipo_entrega="RETIRADA",
        order_items=[SimpleNamespace(
            name="Etiqueta de teste",
            quantity=1,
            subtotal_cents=0,
            note=f"Bobina de {paper_width_mm} mm. Imprima em tamanho real (100%).",
        )],
    )
    output = BytesIO()
    render_ticket_pdf(sample, output, paper_width_mm=58 if paper_width_mm == "58" else 80)
    return Response(output.getvalue(), media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="etiqueta-teste-{paper_width_mm}mm.pdf"',
        "Cache-Control": "private, no-store",
    })


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
            primary_color="#dc2626",
        )
    return PublicSettingsResponse(
        tenant_id=settings.tenant_id,
        cover_image_url=settings.cover_image_url,
        cover_video_url=settings.cover_video_url,
        logo_url=settings.logo_url,
        theme=appearance_service.theme_mode(settings.theme),
        primary_color="#dc2626" if appearance_service.is_legacy_default(settings.theme, settings.primary_color) else settings.primary_color or "#dc2626",
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
    settings.theme = appearance_service.with_theme_mode(settings.theme, payload.theme or "white")
    settings.primary_color = payload.primary_color or "#dc2626"

    db.commit()
    db.refresh(settings)

    return PublicSettingsResponse(
        tenant_id=settings.tenant_id,
        cover_image_url=settings.cover_image_url,
        cover_video_url=settings.cover_video_url,
        logo_url=settings.logo_url,
        theme=appearance_service.theme_mode(settings.theme),
        primary_color="#dc2626" if appearance_service.is_legacy_default(settings.theme, settings.primary_color) else settings.primary_color,
    )
