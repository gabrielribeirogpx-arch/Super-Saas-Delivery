from __future__ import annotations

import uuid
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.models.whatsapp_config import WhatsAppConfig
from app.models.whatsapp_message_log import WhatsAppMessageLog
from app.whatsapp.base import WhatsAppProvider, safe_json, sanitize_payload


class MockWhatsAppProvider(WhatsAppProvider):
    def send_text(
        self,
        db: Session,
        *,
        tenant_id: int,
        config: WhatsAppConfig | None,
        to_phone: str,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> WhatsAppMessageLog:
        payload = {
            "type": "text",
            "to": to_phone,
            "text": text,
            "context": context or {},
        }
        return self._create_log(
            db,
            tenant_id=tenant_id,
            direction="out",
            to_phone=to_phone,
            from_phone=(config.phone_number_id if config else None),
            template_name=None,
            message_type="text",
            payload=payload,
            status="sent",
            provider_message_id=f"mock-{uuid.uuid4().hex[:10]}",
        )

    def send_template(
        self,
        db: Session,
        *,
        tenant_id: int,
        config: WhatsAppConfig | None,
        to_phone: str,
        template_name: str,
        variables: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> WhatsAppMessageLog:
        payload = {
            "type": "template",
            "to": to_phone,
            "template": template_name,
            "variables": variables,
            "context": context or {},
        }
        return self._create_log(
            db,
            tenant_id=tenant_id,
            direction="out",
            to_phone=to_phone,
            from_phone=(config.phone_number_id if config else None),
            template_name=template_name,
            message_type="template",
            payload=payload,
            status="sent",
            provider_message_id=f"mock-{uuid.uuid4().hex[:10]}",
        )

    def send_interactive(
        self,
        db: Session,
        *,
        tenant_id: int,
        config: WhatsAppConfig | None,
        to_phone: str,
        payload: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> WhatsAppMessageLog:
        payload = {
            "type": "interactive",
            "to": to_phone,
            "interactive": payload,
            "context": context or {},
        }
        return self._create_log(
            db,
            tenant_id=tenant_id,
            direction="out",
            to_phone=to_phone,
            from_phone=(config.phone_number_id if config else None),
            template_name=None,
            message_type="interactive",
            payload=payload,
            status="sent",
            provider_message_id=f"mock-{uuid.uuid4().hex[:10]}",
        )

    def parse_webhook(self, payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
        message = payload.get("message") or {}
        if not message:
            return []
        return [
            {
                "message_id": message.get("id") or f"mock-{uuid.uuid4().hex[:8]}",
                "from_number": message.get("from"),
                "text": message.get("text", ""),
                "message_type": message.get("type", "text"),
                "contact_name": message.get("contact_name"),
            }
        ]

    def _create_log(
        self,
        db: Session,
        *,
        tenant_id: int,
        direction: str,
        to_phone: str | None,
        from_phone: str | None,
        template_name: str | None,
        message_type: str,
        payload: dict[str, Any],
        status: str,
        provider_message_id: str | None = None,
        error: str | None = None,
    ) -> WhatsAppMessageLog:
        sanitized = sanitize_payload(payload)
        log_entry = WhatsAppMessageLog(
            tenant_id=tenant_id,
            direction=direction,
            to_phone=to_phone,
            from_phone=from_phone,
            template_name=template_name,
            message_type=message_type,
            payload_json=safe_json(sanitized),
            status=status,
            error=error,
            provider_message_id=provider_message_id,
        )
        db.add(log_entry)
        db.commit()
        return log_entry
