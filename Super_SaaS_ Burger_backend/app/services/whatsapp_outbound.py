from __future__ import annotations

import json
import logging
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.models.whatsapp_message_log import WhatsAppMessageLog
from app.services.admin_audit import log_admin_action
from app.services.customer_stats import is_customer_opted_in
from app.services.whatsapp_templates import TEMPLATES
from app.whatsapp.service import WhatsAppService

logger = logging.getLogger(__name__)


def _format_currency(cents: int) -> str:
    value = (int(cents or 0)) / 100
    formatted = f"{value:,.2f}"
    return f"R$ {formatted}".replace(",", "X").replace(".", ",").replace("X", ".")


def _render_template(template: str, variables: Mapping[str, Any]) -> str:
    if template not in TEMPLATES:
        raise KeyError(f"Template inválido: {template}")
    return TEMPLATES[template].format(**variables)


def send_whatsapp_message(
    db: Session,
    *,
    tenant_id: int,
    phone: str,
    template: str,
    variables: Mapping[str, Any],
    order_id: int | None = None,
) -> WhatsAppMessageLog | None:
    variables_payload = dict(variables)
    if "order_total" not in variables_payload:
        total_cents = int(variables_payload.get("total_cents", 0) or 0)
        variables_payload["order_total"] = _format_currency(total_cents)
    if "customer_name" not in variables_payload:
        variables_payload["customer_name"] = "Cliente"
    if "estimated_time" not in variables_payload:
        variables_payload["estimated_time"] = "30 min"

    if not is_customer_opted_in(db, tenant_id, phone):
        log_entry = WhatsAppMessageLog(
            tenant_id=tenant_id,
            direction="out",
            to_phone=phone,
            from_phone=None,
            template_name=template,
            message_type="template",
            payload_json=json.dumps(
                {"variables": variables_payload, "order_id": order_id, "status_stage": template},
                ensure_ascii=False,
            ),
            status="failed",
            error="opt_out",
            provider_message_id=None,
        )
        db.add(log_entry)
        log_admin_action(
            db,
            tenant_id=tenant_id,
            user_id=0,
            action="whatsapp.outbound.skipped",
            entity_type="order",
            entity_id=order_id,
            meta={"phone": phone, "template": template},
        )
        db.commit()
        logger.info("WhatsApp outbound skipped (opt-out): %s", phone)
        return log_entry

    message_text = _render_template(template, variables_payload)
    logger.info("WhatsApp outbound: %s", message_text)

    service = WhatsAppService()
    log_entry = service.send_template(
        db,
        tenant_id=tenant_id,
        to_phone=phone,
        template_name=template,
        variables={**variables_payload, "rendered_text": message_text},
        order_id=order_id,
        status_stage=template,
    )

    if log_entry:
        log_admin_action(
            db,
            tenant_id=tenant_id,
            user_id=0,
            action="whatsapp.outbound.sent",
            entity_type="order",
            entity_id=order_id,
            meta={"phone": phone, "template": template},
        )
        db.commit()
        return log_entry

    log_admin_action(
        db,
        tenant_id=tenant_id,
        user_id=0,
        action="whatsapp.outbound.duplicate",
        entity_type="order",
        entity_id=order_id,
        meta={"phone": phone, "template": template},
    )
    db.commit()
    return None
