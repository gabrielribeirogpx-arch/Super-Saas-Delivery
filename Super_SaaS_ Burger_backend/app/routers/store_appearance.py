from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.tenant_public_settings import TenantPublicSettings
from app.services.appearance import (
    DEFAULT_APPEARANCE,
    build_appearance_payload,
    merge_appearance_into_theme,
    validate_appearance,
)

router = APIRouter(prefix="/api/store", tags=["store-appearance"])


class AppearancePayload(BaseModel):
    primary_color: str = DEFAULT_APPEARANCE["primary_color"]
    secondary_color: str = DEFAULT_APPEARANCE["secondary_color"]
    hero_mode: str = DEFAULT_APPEARANCE["hero_mode"]
    hero_title: str = DEFAULT_APPEARANCE["hero_title"]
    hero_subtitle: str = DEFAULT_APPEARANCE["hero_subtitle"]
    logo_url: str = DEFAULT_APPEARANCE["logo_url"]
    cover_url: str = DEFAULT_APPEARANCE["cover_url"]
    button_style: str = DEFAULT_APPEARANCE["button_style"]
    layout_mode: str = DEFAULT_APPEARANCE["layout_mode"]


class AppearanceResponse(AppearancePayload):
    tenant_id: int


@router.get("/appearance", response_model=AppearanceResponse)
def get_store_appearance(
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    settings = (
        db.query(TenantPublicSettings)
        .filter(TenantPublicSettings.tenant_id == user.tenant_id)
        .first()
    )
    appearance = build_appearance_payload(
        theme_value=settings.theme if settings else None,
        primary_color=settings.primary_color if settings else None,
        logo_url=settings.logo_url if settings else None,
        cover_image_url=settings.cover_image_url if settings else None,
    )
    return AppearanceResponse(tenant_id=user.tenant_id, **appearance)


@router.put("/appearance", response_model=AppearanceResponse)
def update_store_appearance(
    payload: AppearancePayload,
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

    try:
        appearance = validate_appearance(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    settings.theme = merge_appearance_into_theme(settings.theme, appearance)
    settings.primary_color = appearance["primary_color"]
    settings.logo_url = appearance["logo_url"] or None
    settings.cover_image_url = appearance["cover_url"] or None

    db.commit()
    db.refresh(settings)

    return AppearanceResponse(tenant_id=user.tenant_id, **appearance)
