from __future__ import annotations

import re
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.tenant_public_settings import TenantPublicSettings

router = APIRouter(prefix="/api/store/theme", tags=["store-theme"])

UPLOADS_DIR = Path("uploads")
HEX_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
URL_PATTERN = re.compile(r"^https?://")


class StoreThemePayload(BaseModel):
    primary_color: str | None = None
    accent_color: str | None = None
    background_color: str | None = None
    surface_color: str | None = None
    button_radius: int | None = Field(default=None, ge=6, le=32)
    card_radius: int | None = Field(default=None, ge=6, le=32)
    cover_image_url: str | None = None
    logo_url: str | None = None
    hero_overlay_opacity: float | None = Field(default=None, ge=0, le=0.9)

    @field_validator("primary_color", "accent_color", "background_color", "surface_color")
    @classmethod
    def validate_hex(cls, value: str | None) -> str | None:
        if value is None:
            return value
        candidate = value.strip()
        if not HEX_PATTERN.match(candidate):
            raise ValueError("Cor inválida. Use hexadecimal no formato #RRGGBB.")
        return candidate

    @field_validator("cover_image_url", "logo_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        candidate = value.strip()
        if not candidate:
            return None
        if not URL_PATTERN.match(candidate):
            raise ValueError("URL inválida. Use http:// ou https://")
        return candidate


class StoreThemeResponse(StoreThemePayload):
    tenant_id: int


class UploadResponse(BaseModel):
    url: str


def _save_upload(upload: UploadFile) -> str:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(upload.filename or "").suffix
    filename = f"{uuid4().hex}{suffix}"
    path = UPLOADS_DIR / filename
    with path.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    return f"/uploads/{filename}"


@router.post("/upload", response_model=UploadResponse)
def upload_theme_image(
    image: UploadFile = File(...),
    _user: AdminUser = Depends(require_role(["admin", "owner"])),
):
    if not (image.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Envie um arquivo de imagem válido")
    return UploadResponse(url=_save_upload(image))


@router.get("", response_model=StoreThemeResponse)
def get_store_theme(
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    settings = (
        db.query(TenantPublicSettings)
        .filter(TenantPublicSettings.tenant_id == user.tenant_id)
        .first()
    )
    if not settings:
        return StoreThemeResponse(tenant_id=user.tenant_id)

    return StoreThemeResponse(
        tenant_id=settings.tenant_id,
        primary_color=settings.primary_color,
        accent_color=settings.accent_color,
        background_color=settings.background_color,
        surface_color=settings.surface_color,
        button_radius=settings.button_radius,
        card_radius=settings.card_radius,
        cover_image_url=settings.cover_image_url,
        logo_url=settings.logo_url,
        hero_overlay_opacity=settings.hero_overlay_opacity,
    )


@router.put("", response_model=StoreThemeResponse)
def update_store_theme(
    payload: StoreThemePayload,
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

    settings.primary_color = payload.primary_color
    settings.accent_color = payload.accent_color
    settings.background_color = payload.background_color
    settings.surface_color = payload.surface_color
    settings.button_radius = payload.button_radius
    settings.card_radius = payload.card_radius
    settings.cover_image_url = payload.cover_image_url
    settings.logo_url = payload.logo_url
    settings.hero_overlay_opacity = payload.hero_overlay_opacity

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível salvar o tema da loja",
        ) from exc

    db.refresh(settings)
    return StoreThemeResponse(
        tenant_id=settings.tenant_id,
        primary_color=settings.primary_color,
        accent_color=settings.accent_color,
        background_color=settings.background_color,
        surface_color=settings.surface_color,
        button_radius=settings.button_radius,
        card_radius=settings.card_radius,
        cover_image_url=settings.cover_image_url,
        logo_url=settings.logo_url,
        hero_overlay_opacity=settings.hero_overlay_opacity,
    )
