from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Protocol

from sqlalchemy.orm import Session

from app.models.whatsapp_config import WhatsAppConfig
from app.models.whatsapp_message_log import WhatsAppMessageLog


@dataclass
class WhatsAppSendResult:
    status: str
    provider_message_id: str | None = None
    error: str | None = None
    response_payload: dict[str, Any] | None = None


class WhatsAppProvider(Protocol):
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
        ...

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
        ...

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
        ...

    def parse_webhook(self, payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
        ...


SENSITIVE_KEYS = {"access_token", "verify_token", "webhook_secret", "authorization", "token"}


def _mask_value(value: Any) -> Any:
    if value is None:
        return None
    text = str(value)
    if len(text) <= 4:
        return "****"
    return f"****{text[-4:]}"


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    def _sanitize(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: _sanitize_value(key, inner) for key, inner in value.items()}
        if isinstance(value, list):
            return [_sanitize(item) for item in value]
        return value

    def _sanitize_value(key: str, value: Any) -> Any:
        if key.lower() in SENSITIVE_KEYS:
            return _mask_value(value)
        return _sanitize(value)

    return _sanitize(payload)


def safe_json(payload: dict[str, Any]) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        return "{}"
