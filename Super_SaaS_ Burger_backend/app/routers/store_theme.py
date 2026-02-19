from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_request_tenant_id, require_role
from app.models.admin_user import AdminUser
from app.models.store_theme import StoreTheme

router = APIRouter(prefix="/api/store/theme", tags=["store-theme"])

HEX_COLOR_PATTERN = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")


class StoreThemePayload(BaseModel):
    primary_color: str | None = None
    secondary_color: str | None = None
    logo_url: str | None = None
    cover_url: str | None = None
    slogan: str | None = None
    show_logo_on_cover: bool = True


class StoreThemeResponse(StoreThemePayload):
    updated_at: str | None = None


def _normalize_color(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if not HEX_COLOR_PATTERN.match(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} deve estar em hexadecimal (#RGB ou #RRGGBB)",
        )
    return normalized


def _build_response(theme: StoreTheme | None) -> StoreThemeResponse:
    if not theme:
        return StoreThemeResponse(
            primary_color="#2563EB",
            secondary_color=None,
            logo_url=None,
            cover_url=None,
            slogan=None,
            show_logo_on_cover=True,
            updated_at=None,
        )
    return StoreThemeResponse(
        primary_color=theme.primary_color or "#2563EB",
        secondary_color=theme.secondary_color,
        logo_url=theme.logo_url,
        cover_url=theme.cover_url,
        slogan=theme.slogan,
        show_logo_on_cover=bool(theme.show_logo_on_cover),
        updated_at=theme.updated_at.isoformat() if theme.updated_at else None,
    )


@router.get("", response_model=StoreThemeResponse)
def get_store_theme(
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
):
    theme = db.query(StoreTheme).filter(StoreTheme.tenant_id == tenant_id).first()
    return _build_response(theme)


@router.put("", response_model=StoreThemeResponse)
def upsert_store_theme(
    payload: StoreThemePayload,
    tenant_id: int = Depends(get_request_tenant_id),
    _user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    theme = db.query(StoreTheme).filter(StoreTheme.tenant_id == tenant_id).first()
    if not theme:
        theme = StoreTheme(tenant_id=tenant_id)
        db.add(theme)

    theme.primary_color = _normalize_color(payload.primary_color, "primary_color")
    theme.secondary_color = _normalize_color(payload.secondary_color, "secondary_color")
    theme.logo_url = payload.logo_url.strip() if payload.logo_url else None
    theme.cover_url = payload.cover_url.strip() if payload.cover_url else None
    theme.slogan = payload.slogan.strip() if payload.slogan else None
    theme.show_logo_on_cover = payload.show_logo_on_cover

    db.commit()
    db.refresh(theme)

    return _build_response(theme)
