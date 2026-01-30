from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.ai.gemini_provider import GeminiProvider
from app.ai.mock_provider import MockProvider
from app.ai.schema import AssistantResponse
from app.ai import tools
from app.models.ai_config import AIConfig
from app.models.ai_message_log import AIMessageLog
from app.models.menu_item import MenuItem
from app.models.menu_item_modifier_group import MenuItemModifierGroup
from app.models.modifier import Modifier
from app.models.modifier_group import ModifierGroup

logger = logging.getLogger(__name__)


def get_ai_config(db: Session, tenant_id: int) -> AIConfig:
    config = db.query(AIConfig).filter(AIConfig.tenant_id == tenant_id).first()
    if not config:
        config = AIConfig(tenant_id=tenant_id, provider="mock", enabled=False)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def get_provider(tenant_id: int, db: Session) -> AIProvider:
    config = get_ai_config(db, tenant_id)
    provider = (config.provider or "mock").strip().lower()
    if provider == "gemini":
        return GeminiProvider()
    return MockProvider()


def build_context(tenant_id: int, db: Session) -> dict[str, Any]:
    menu_items = (
        db.query(MenuItem)
        .filter(MenuItem.tenant_id == tenant_id, MenuItem.active.is_(True))
        .order_by(MenuItem.id.asc())
        .limit(25)
        .all()
    )
    modifiers = (
        db.query(Modifier)
        .filter(Modifier.tenant_id == tenant_id, Modifier.active.is_(True))
        .order_by(Modifier.id.asc())
        .all()
    )
    modifier_groups = (
        db.query(ModifierGroup)
        .filter(ModifierGroup.tenant_id == tenant_id, ModifierGroup.active.is_(True))
        .order_by(ModifierGroup.id.asc())
        .all()
    )
    item_groups = (
        db.query(MenuItemModifierGroup)
        .filter(MenuItemModifierGroup.tenant_id == tenant_id)
        .all()
    )

    return {
        "menu_items": [
            {
                "id": item.id,
                "name": item.name,
                "price_cents": item.price_cents,
                "category_id": item.category_id,
                "aliases": [item.name],
            }
            for item in menu_items
        ],
        "modifiers": [
            {
                "id": modifier.id,
                "name": modifier.name,
                "price_cents": modifier.price_cents,
                "group_id": modifier.group_id,
            }
            for modifier in modifiers
        ],
        "modifier_groups": [
            {"id": group.id, "name": group.name} for group in modifier_groups
        ],
        "item_modifier_groups": [
            {"menu_item_id": entry.menu_item_id, "modifier_group_id": entry.modifier_group_id}
            for entry in item_groups
        ],
        "business_rules": {
            "mandatory_modifier_groups": False,
            "notes": "Use apenas ferramentas disponíveis do sistema.",
        },
    }


def _fallback_rule_parser(message: str, context: dict[str, Any]) -> AssistantResponse:
    fallback_provider = MockProvider()
    response = fallback_provider.generate(tenant_id=0, phone="", user_message=message, context=context)
    return AssistantResponse.parse_obj(response)


def _log_message(
    db: Session,
    *,
    tenant_id: int,
    phone: str,
    direction: str,
    provider: str,
    prompt: str | None = None,
    raw_response: str | None = None,
    parsed_json: str | None = None,
    error: str | None = None,
) -> None:
    entry = AIMessageLog(
        tenant_id=tenant_id,
        phone=phone,
        direction=direction,
        provider=provider,
        prompt=prompt,
        raw_response=raw_response,
        parsed_json=parsed_json,
        error=error,
    )
    db.add(entry)
    db.commit()


def run_assistant(
    tenant_id: int,
    phone: str,
    message: str,
    db: Session,
) -> tuple[dict[str, Any], str]:
    config = get_ai_config(db, tenant_id)
    provider = get_provider(tenant_id, db)
    context = build_context(tenant_id, db)

    prompt_payload = {
        "system_prompt": (config.system_prompt or "").strip(),
        "user_message": message,
        "context": context,
    }
    prompt_text = json.dumps(prompt_payload, ensure_ascii=False)

    _log_message(
        db,
        tenant_id=tenant_id,
        phone=phone,
        direction="in",
        provider=provider.name,
        prompt=message,
    )

    raw_response = None
    parsed_response: AssistantResponse | None = None
    error_message = None

    try:
        raw_payload = provider.generate(tenant_id, phone, message, context)
        raw_response = json.dumps(raw_payload, ensure_ascii=False)
        parsed_response = AssistantResponse.parse_obj(raw_payload)
    except ValidationError as exc:
        error_message = f"validation_error: {exc}"
        parsed_response = _fallback_rule_parser(message, context)
    except Exception as exc:
        error_message = f"provider_error: {exc}"
        parsed_response = _fallback_rule_parser(message, context)

    final_message = parsed_response.message_to_user
    tool_errors: list[str] = []
    tool_messages: list[str] = []

    for call in parsed_response.tool_calls:
        name = call.name
        args = call.args or {}
        try:
            if name == "ensure_open_order":
                order = tools.ensure_open_order(db, tenant_id, phone)
                tool_messages.append(f"Pedido aberto #{order.id}.")
            elif name == "add_item":
                result = tools.add_item(
                    db,
                    tenant_id,
                    phone,
                    item_id=args.get("item_id"),
                    item_name=args.get("item_name"),
                    qty=args.get("qty"),
                    modifiers=args.get("modifiers"),
                )
                if result.get("message"):
                    tool_messages.append(result["message"])
            elif name == "list_menu":
                result = tools.list_menu(db, tenant_id)
                if result.get("message"):
                    tool_messages.append(result["message"])
            elif name == "checkout":
                result = tools.checkout(db, tenant_id, phone, order_id=args.get("order_id"))
                if result.get("message"):
                    tool_messages.append(result["message"])
            elif name == "order_status":
                result = tools.order_status(db, tenant_id, phone)
                if result.get("message"):
                    tool_messages.append(result["message"])
            else:
                tool_errors.append(f"tool_not_found:{name}")
        except Exception as exc:
            logger.exception("Erro executando tool_call %s", name)
            tool_errors.append(f"tool_error:{name}:{exc}")

    if tool_messages:
        final_message = tool_messages[-1]

    if tool_errors:
        combined = "; ".join(tool_errors)
        error_message = f"{error_message or ''} {combined}".strip()

    parsed_json = json.dumps(parsed_response.dict(), ensure_ascii=False)

    _log_message(
        db,
        tenant_id=tenant_id,
        phone=phone,
        direction="out",
        provider=provider.name,
        prompt=prompt_text,
        raw_response=raw_response,
        parsed_json=parsed_json,
        error=error_message,
    )

    return parsed_response.dict(), final_message
