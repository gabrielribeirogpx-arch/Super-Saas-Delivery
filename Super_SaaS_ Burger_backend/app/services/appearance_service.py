from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.tenant_public_settings import TenantPublicSettings
from app.schemas.appearance import AppearanceSettings

_APPEARANCE_PREFIX = "appearance:v1:"


class AppearanceService:
    @staticmethod
    def _to_settings(raw_value: Any) -> AppearanceSettings:
        if not isinstance(raw_value, str) or not raw_value.startswith(_APPEARANCE_PREFIX):
            return AppearanceSettings()

        payload = raw_value[len(_APPEARANCE_PREFIX):]
        try:
            parsed = json.loads(payload)
        except (TypeError, ValueError, json.JSONDecodeError):
            return AppearanceSettings()

        if not isinstance(parsed, dict):
            return AppearanceSettings()

        try:
            return AppearanceSettings(**parsed)
        except Exception:
            return AppearanceSettings()

    @staticmethod
    def _serialize(settings: AppearanceSettings) -> str:
        return f"{_APPEARANCE_PREFIX}{json.dumps(settings.model_dump(mode='json'))}"

    def get_appearance(self, db: Session, tenant_id: int) -> AppearanceSettings:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        settings = (
            db.query(TenantPublicSettings)
            .filter(TenantPublicSettings.tenant_id == tenant_id)
            .first()
        )
        banner_blur_enabled = True if tenant is None else bool(tenant.banner_blur_enabled)
        if not settings:
            return AppearanceSettings(banner_blur_enabled=banner_blur_enabled)

        theme_value = getattr(settings, "theme", None)
        payload = self._to_settings(theme_value)
        return payload.model_copy(update={"banner_blur_enabled": banner_blur_enabled})

    def update_appearance(
        self,
        db: Session,
        tenant_id: int,
        data: AppearanceSettings,
    ) -> AppearanceSettings:
        payload = AppearanceSettings(**data.model_dump())
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        settings = (
            db.query(TenantPublicSettings)
            .filter(TenantPublicSettings.tenant_id == tenant_id)
            .first()
        )

        if not settings:
            settings = TenantPublicSettings(tenant_id=tenant_id)
            db.add(settings)

        if hasattr(settings, "theme"):
            settings.theme = self._serialize(payload)

        if hasattr(settings, "primary_color"):
            settings.primary_color = payload.primary_color

        if hasattr(settings, "logo_url"):
            settings.logo_url = payload.logo_url

        if tenant is not None:
            tenant.banner_blur_enabled = payload.banner_blur_enabled

        db.commit()
        if tenant is not None:
            db.refresh(tenant)
        db.refresh(settings)
        response = self._to_settings(getattr(settings, "theme", None))
        return response.model_copy(
            update={"banner_blur_enabled": True if tenant is None else bool(tenant.banner_blur_enabled)}
        )


appearance_service = AppearanceService()
