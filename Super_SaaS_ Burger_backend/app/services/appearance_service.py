from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.tenant_public_settings import TenantPublicSettings
from app.schemas.appearance import AppearanceSettings

_APPEARANCE_PREFIX = "appearance:v1:"


class AppearanceService:
    @staticmethod
    def theme_mode(raw_value: Any) -> str:
        if raw_value == "dark":
            return "dark"
        if isinstance(raw_value, str) and raw_value.startswith(_APPEARANCE_PREFIX):
            try:
                payload = json.loads(raw_value[len(_APPEARANCE_PREFIX):])
                if isinstance(payload, dict) and payload.get("_theme_mode") == "dark":
                    return "dark"
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        return "white"

    @staticmethod
    def with_theme_mode(raw_value: Any, mode: str) -> str:
        if isinstance(raw_value, str) and raw_value.startswith(_APPEARANCE_PREFIX):
            try:
                payload = json.loads(raw_value[len(_APPEARANCE_PREFIX):])
                if isinstance(payload, dict):
                    payload["_theme_mode"] = "dark" if mode == "dark" else "white"
                    return f"{_APPEARANCE_PREFIX}{json.dumps(payload)}"
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        return "dark" if mode == "dark" else "white"

    @staticmethod
    def is_legacy_default(raw_value: Any, primary_color: str | None) -> bool:
        """Identify the old untouched blue preset without replacing custom palettes."""
        if primary_color != "#2563eb" or not isinstance(raw_value, str) or not raw_value.startswith(_APPEARANCE_PREFIX):
            return False
        try:
            parsed = json.loads(raw_value[len(_APPEARANCE_PREFIX):])
            if not isinstance(parsed, dict) or parsed.get("primary_color") != "#2563eb" or parsed.get("_color_explicit"):
                return False
            legacy = AppearanceSettings(**parsed)
            baseline = AppearanceSettings(primary_color="#2563eb")
            return legacy.model_dump() == baseline.model_dump()
        except (TypeError, ValueError, json.JSONDecodeError):
            return False

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
    def _serialize(settings: AppearanceSettings, *, color_explicit: bool = False, theme_mode: str = "white") -> str:
        payload = settings.model_dump(mode="json")
        if color_explicit:
            payload["_color_explicit"] = True
        payload["_theme_mode"] = "dark" if theme_mode == "dark" else "white"
        return f"{_APPEARANCE_PREFIX}{json.dumps(payload)}"

    def get_appearance(self, db: Session, tenant_id: int) -> AppearanceSettings:
        settings = (
            db.query(TenantPublicSettings)
            .filter(TenantPublicSettings.tenant_id == tenant_id)
            .first()
        )
        if not settings:
            return AppearanceSettings()

        theme_value = getattr(settings, "theme", None)
        # Only the new onboarding profile uses the Fomizero defaults.
        # Keep legacy/null and serialized custom appearances unchanged.
        if theme_value == "white" and settings.primary_color == "#dc2626":
            return AppearanceSettings(primary_color=settings.primary_color)
        if self.is_legacy_default(theme_value, settings.primary_color):
            return AppearanceSettings()
        return self._to_settings(theme_value)

    def update_appearance(
        self,
        db: Session,
        tenant_id: int,
        data: AppearanceSettings,
    ) -> AppearanceSettings:
        provided_fields = set(getattr(data, "model_fields_set", set()))
        payload = AppearanceSettings(**data.model_dump())
        settings = (
            db.query(TenantPublicSettings)
            .filter(TenantPublicSettings.tenant_id == tenant_id)
            .first()
        )

        if not settings:
            settings = TenantPublicSettings(tenant_id=tenant_id)
            db.add(settings)

        if hasattr(settings, "theme"):
            settings.theme = self._serialize(payload, color_explicit=True, theme_mode=self.theme_mode(settings.theme))

        if hasattr(settings, "primary_color"):
            settings.primary_color = payload.primary_color

        if hasattr(settings, "logo_url") and "logo_url" in provided_fields:
            settings.logo_url = payload.logo_url

        db.commit()
        db.refresh(settings)

        return self._to_settings(getattr(settings, "theme", None))


appearance_service = AppearanceService()
