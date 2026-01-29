from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import IS_DEV
from app.models.whatsapp_config import WhatsAppConfig
from app.models.whatsapp_message_log import WhatsAppMessageLog
from app.whatsapp.base import WhatsAppProvider
from app.whatsapp.base import sanitize_payload, safe_json
from app.whatsapp.cloud_provider import CloudWhatsAppProvider
from app.whatsapp.mock_provider import MockWhatsAppProvider

logger = logging.getLogger(__name__)


class WhatsAppService:
    def __init__(self) -> None:
        self._mock_provider = MockWhatsAppProvider()
        self._cloud_provider = CloudWhatsAppProvider()

    def get_config(self, db: Session, tenant_id: int) -> WhatsAppConfig | None:
        return (
            db.query(WhatsAppConfig)
            .filter(WhatsAppConfig.tenant_id == tenant_id)
            .first()
        )

    def _select_provider(
        self,
        config: WhatsAppConfig | None,
    ) -> WhatsAppProvider:
        if not config or not config.is_enabled:
            return self._mock_provider
        if config.provider == "cloud" and config.access_token and config.phone_number_id:
            return self._cloud_provider
        return self._mock_provider

    def _should_fallback(self) -> bool:
        return IS_DEV

    def _is_duplicate_template(
        self,
        db: Session,
        *,
        tenant_id: int,
        template_name: str,
        order_id: int | None,
        status_stage: str | None,
    ) -> bool:
        if not order_id:
            return False
        query = (
            db.query(WhatsAppMessageLog)
            .filter(
                WhatsAppMessageLog.tenant_id == tenant_id,
                WhatsAppMessageLog.direction == "out",
                WhatsAppMessageLog.template_name == template_name,
                WhatsAppMessageLog.status != "failed",
            )
        )
        marker = f'"order_id": {order_id}'
        query = query.filter(WhatsAppMessageLog.payload_json.contains(marker))
        if status_stage:
            stage_marker = f'"status_stage": "{status_stage}"'
            query = query.filter(WhatsAppMessageLog.payload_json.contains(stage_marker))
        existing = query.first()
        return existing is not None

    def send_text(
        self,
        db: Session,
        *,
        tenant_id: int,
        to_phone: str,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> WhatsAppMessageLog:
        config = self.get_config(db, tenant_id)
        provider = self._select_provider(config)
        log_entry = provider.send_text(
            db,
            tenant_id=tenant_id,
            config=config,
            to_phone=to_phone,
            text=text,
            context=context,
        )
        if log_entry.status == "failed" and provider is self._cloud_provider and self._should_fallback():
            logger.warning("WhatsApp Cloud falhou, usando mock (tenant=%s)", tenant_id)
            return self._mock_provider.send_text(
                db,
                tenant_id=tenant_id,
                config=config,
                to_phone=to_phone,
                text=text,
                context={"fallback": "mock", **(context or {})},
            )
        return log_entry

    def send_template(
        self,
        db: Session,
        *,
        tenant_id: int,
        to_phone: str,
        template_name: str,
        variables: dict[str, Any],
        order_id: int | None = None,
        status_stage: str | None = None,
    ) -> WhatsAppMessageLog | None:
        if self._is_duplicate_template(
            db,
            tenant_id=tenant_id,
            template_name=template_name,
            order_id=order_id,
            status_stage=status_stage,
        ):
            logger.info("WhatsApp idempotente: tenant=%s template=%s order=%s", tenant_id, template_name, order_id)
            return None

        config = self.get_config(db, tenant_id)
        provider = self._select_provider(config)
        context = {
            "order_id": order_id,
            "status_stage": status_stage or template_name,
        }
        payload_vars = dict(variables)
        payload_vars["order_id"] = order_id
        payload_vars["status_stage"] = status_stage or template_name

        log_entry = provider.send_template(
            db,
            tenant_id=tenant_id,
            config=config,
            to_phone=to_phone,
            template_name=template_name,
            variables=payload_vars,
            context=context,
        )
        if log_entry.status == "failed" and provider is self._cloud_provider and self._should_fallback():
            logger.warning("WhatsApp Cloud falhou, usando mock (tenant=%s)", tenant_id)
            return self._mock_provider.send_template(
                db,
                tenant_id=tenant_id,
                config=config,
                to_phone=to_phone,
                template_name=template_name,
                variables=payload_vars,
                context={"fallback": "mock", **context},
            )
        return log_entry

    def send_interactive(
        self,
        db: Session,
        *,
        tenant_id: int,
        to_phone: str,
        payload: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> WhatsAppMessageLog:
        config = self.get_config(db, tenant_id)
        provider = self._select_provider(config)
        log_entry = provider.send_interactive(
            db,
            tenant_id=tenant_id,
            config=config,
            to_phone=to_phone,
            payload=payload,
            context=context,
        )
        if log_entry.status == "failed" and provider is self._cloud_provider and self._should_fallback():
            logger.warning("WhatsApp Cloud falhou, usando mock (tenant=%s)", tenant_id)
            return self._mock_provider.send_interactive(
                db,
                tenant_id=tenant_id,
                config=config,
                to_phone=to_phone,
                payload=payload,
                context={"fallback": "mock", **(context or {})},
            )
        return log_entry

    def log_inbound(
        self,
        db: Session,
        *,
        tenant_id: int,
        from_phone: str,
        to_phone: str | None,
        message_type: str,
        payload: dict[str, Any],
        provider_message_id: str | None = None,
    ) -> WhatsAppMessageLog:
        log_entry = WhatsAppMessageLog(
            tenant_id=tenant_id,
            direction="in",
            to_phone=to_phone,
            from_phone=from_phone,
            template_name=None,
            message_type=message_type,
            payload_json=safe_json(sanitize_payload(payload)),
            status="received",
            error=None,
            provider_message_id=provider_message_id,
        )
        db.add(log_entry)
        db.commit()
        return log_entry
