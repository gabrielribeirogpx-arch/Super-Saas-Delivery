from __future__ import annotations

import json
import logging
import time
from typing import Any, Iterable

import httpx
from sqlalchemy.orm import Session

from app.core.config import META_API_VERSION
from app.models.whatsapp_config import WhatsAppConfig
from app.models.whatsapp_message_log import WhatsAppMessageLog
from app.services.tenant_backoff import InMemoryTenantBackoffService
from app.whatsapp.base import WhatsAppProvider, safe_json, sanitize_payload

logger = logging.getLogger(__name__)
_backoff_service = InMemoryTenantBackoffService()


def parse_cloud_webhook(payload: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value") or {}
            metadata = value.get("metadata") or {}
            phone_number_id = metadata.get("phone_number_id")
            display_phone_number = metadata.get("display_phone_number")

            contacts = value.get("contacts") or []
            contact_name = None
            if contacts:
                contact_name = ((contacts[0].get("profile") or {}).get("name")) or None

            for msg in value.get("messages", []) or []:
                msg_type = msg.get("type") or "text"
                text = ""
                if msg_type == "text":
                    text = ((msg.get("text") or {}).get("body")) or ""
                message_id = msg.get("id")
                from_number = msg.get("from")
                if not message_id or not from_number:
                    continue
                messages.append(
                    {
                        "message_id": message_id,
                        "from_number": from_number,
                        "text": text.strip(),
                        "message_type": msg_type,
                        "phone_number_id": phone_number_id,
                        "display_phone_number": display_phone_number,
                        "contact_name": contact_name,
                    }
                )
    return messages


class CloudWhatsAppProvider(WhatsAppProvider):
    MAX_RETRIES = 3
    INTEGRATION_NAME = "whatsapp_cloud"

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
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        return self._send(
            db,
            tenant_id=tenant_id,
            config=config,
            to_phone=to_phone,
            message_type="text",
            template_name=None,
            payload=payload,
            context=context,
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
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {"preview_url": False, "body": variables.get("rendered_text") or ""},
            "template_name": template_name,
            "template_variables": variables,
        }
        return self._send(
            db,
            tenant_id=tenant_id,
            config=config,
            to_phone=to_phone,
            message_type="template",
            template_name=template_name,
            payload=payload,
            context=context,
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
        body = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "interactive",
            "interactive": payload,
        }
        return self._send(
            db,
            tenant_id=tenant_id,
            config=config,
            to_phone=to_phone,
            message_type="interactive",
            template_name=None,
            payload=body,
            context=context,
        )

    def parse_webhook(self, payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
        return parse_cloud_webhook(payload)

    def _send(
        self,
        db: Session,
        *,
        tenant_id: int,
        config: WhatsAppConfig | None,
        to_phone: str,
        message_type: str,
        template_name: str | None,
        payload: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> WhatsAppMessageLog:
        if not config or not config.access_token or not config.phone_number_id:
            error = "Credenciais do WhatsApp Cloud incompletas"
            return self._create_log(
                db,
                tenant_id=tenant_id,
                direction="out",
                to_phone=to_phone,
                from_phone=None,
                template_name=template_name,
                message_type=message_type,
                payload=payload,
                status="failed",
                error=error,
            )

        url = f"https://graph.facebook.com/{META_API_VERSION}/{config.phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {config.access_token}", "Content-Type": "application/json"}
        payload = dict(payload)
        if context:
            payload["context"] = context

        last_error: str | None = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            decision = _backoff_service.before_request(tenant_id=tenant_id, integration=self.INTEGRATION_NAME)
            if decision.delay_seconds > 0:
                logger.warning(
                    "tenant integration backoff activated",
                    extra={
                        "tenant_id": tenant_id,
                        "integration": self.INTEGRATION_NAME,
                        "delay_seconds": decision.delay_seconds,
                        "consecutive_failures": decision.consecutive_failures,
                    },
                )
                time.sleep(decision.delay_seconds)

            try:
                with httpx.Client(timeout=20.0) as client:
                    response = client.post(url, headers=headers, json=payload)

                body_text = response.text
                if 200 <= response.status_code < 300:
                    _backoff_service.register_success(tenant_id=tenant_id, integration=self.INTEGRATION_NAME)
                    provider_id = None
                    try:
                        data = response.json()
                        provider_id = ((data.get("messages") or [{}])[0].get("id"))
                    except json.JSONDecodeError:
                        data = {"raw": body_text}

                    return self._create_log(
                        db,
                        tenant_id=tenant_id,
                        direction="out",
                        to_phone=to_phone,
                        from_phone=config.phone_number_id,
                        template_name=template_name,
                        message_type=message_type,
                        payload=payload,
                        status="sent",
                        provider_message_id=provider_id,
                        response_payload=data,
                    )

                last_error = f"Erro WhatsApp {response.status_code}: {body_text}"
                failures = _backoff_service.register_failure(tenant_id=tenant_id, integration=self.INTEGRATION_NAME)
                if failures == _backoff_service.threshold:
                    logger.warning(
                        "tenant integration failure threshold reached",
                        extra={
                            "tenant_id": tenant_id,
                            "integration": self.INTEGRATION_NAME,
                            "consecutive_failures": failures,
                        },
                    )
            except Exception as exc:
                last_error = str(exc)
                failures = _backoff_service.register_failure(tenant_id=tenant_id, integration=self.INTEGRATION_NAME)
                if failures == _backoff_service.threshold:
                    logger.warning(
                        "tenant integration failure threshold reached",
                        extra={
                            "tenant_id": tenant_id,
                            "integration": self.INTEGRATION_NAME,
                            "consecutive_failures": failures,
                        },
                    )

            if attempt >= self.MAX_RETRIES:
                break

        return self._create_log(
            db,
            tenant_id=tenant_id,
            direction="out",
            to_phone=to_phone,
            from_phone=config.phone_number_id if config else None,
            template_name=template_name,
            message_type=message_type,
            payload=payload,
            status="failed",
            error=last_error,
        )

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
        response_payload: dict[str, Any] | None = None,
    ) -> WhatsAppMessageLog:
        sanitized = sanitize_payload(payload)
        if response_payload:
            sanitized["response"] = sanitize_payload(response_payload)
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
