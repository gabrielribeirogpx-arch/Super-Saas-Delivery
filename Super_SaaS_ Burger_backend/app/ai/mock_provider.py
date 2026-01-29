from __future__ import annotations

from typing import Any

from app.services.menu_search import normalize


_QUANTITY_WORDS = {
    "um": 1,
    "uma": 1,
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "três": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
}


def _extract_quantity(text: str) -> int:
    tokens = normalize(text).split()
    for token in tokens:
        if token.isdigit():
            return max(int(token), 1)
        if token in _QUANTITY_WORDS:
            return max(_QUANTITY_WORDS[token], 1)
    return 1


def _pick_menu_item(text: str, menu_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not menu_items:
        return None
    normalized_text = normalize(text)
    if not normalized_text:
        return None

    scored: list[tuple[dict[str, Any], int]] = []
    for item in menu_items:
        name = str(item.get("name") or "")
        if not name:
            continue
        normalized_name = normalize(name)
        if not normalized_name:
            continue
        if normalized_name in normalized_text:
            scored.append((item, len(normalized_name)))
            continue
        aliases = item.get("aliases") or []
        for alias in aliases:
            normalized_alias = normalize(str(alias))
            if normalized_alias and normalized_alias in normalized_text:
                scored.append((item, len(normalized_alias)))
                break

    if scored:
        scored.sort(key=lambda entry: entry[1], reverse=True)
        return scored[0][0]

    tokens = set(normalized_text.split())
    best_item = None
    best_score = 0
    for item in menu_items:
        name = str(item.get("name") or "")
        normalized_name = normalize(name)
        if not normalized_name:
            continue
        item_tokens = set(normalized_name.split())
        overlap = len(tokens & item_tokens)
        if overlap > best_score:
            best_score = overlap
            best_item = item

    if best_score >= 2:
        return best_item
    return None


def _extract_modifiers(text: str, modifiers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not modifiers:
        return []
    normalized_text = normalize(text)
    matches = []
    for mod in modifiers:
        name = str(mod.get("name") or "")
        if not name:
            continue
        normalized_name = normalize(name)
        if normalized_name and normalized_name in normalized_text:
            matches.append({"name": name, "price_cents": int(mod.get("price_cents", 0) or 0)})
    return matches


class MockProvider:
    name = "mock"

    def generate(
        self,
        tenant_id: int,
        phone: str,
        user_message: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        text = user_message or ""
        normalized_text = normalize(text)
        menu_items = context.get("menu_items") or []
        modifiers = context.get("modifiers") or []

        if any(token in normalized_text for token in ["cardapio", "cardápio", "menu"]):
            return {
                "intent": "SHOW_MENU",
                "tool_calls": [{"name": "list_menu", "args": {}}],
                "message_to_user": "Aqui está nosso cardápio!",
                "confidence": 0.9,
            }

        if "finalizar" in normalized_text:
            return {
                "intent": "CHECKOUT",
                "tool_calls": [{"name": "checkout", "args": {}}],
                "message_to_user": "Vou finalizar seu pedido. Aguarde um instante!",
                "confidence": 0.85,
            }

        if "status" in normalized_text:
            return {
                "intent": "ORDER_STATUS",
                "tool_calls": [{"name": "order_status", "args": {}}],
                "message_to_user": "Vou verificar o status do seu pedido.",
                "confidence": 0.85,
            }

        if "ajuda" in normalized_text or "help" in normalized_text:
            return {
                "intent": "HELP",
                "tool_calls": [],
                "message_to_user": "Posso mostrar o cardápio, adicionar itens ou finalizar o pedido.",
                "confidence": 0.8,
            }

        picked_item = _pick_menu_item(text, menu_items)
        if "pedir" in normalized_text or picked_item:
            qty = _extract_quantity(text)
            modifiers_payload = _extract_modifiers(text, modifiers)
            if picked_item:
                args = {
                    "item_id": picked_item.get("id"),
                    "item_name": picked_item.get("name"),
                    "qty": qty,
                    "modifiers": modifiers_payload,
                }
                return {
                    "intent": "ADD_ITEM",
                    "tool_calls": [{"name": "add_item", "args": args}],
                    "message_to_user": f"Beleza! Vou adicionar {qty}x {picked_item.get('name')}.",
                    "confidence": 0.82,
                }
            return {
                "intent": "ADD_ITEM",
                "tool_calls": [],
                "message_to_user": "Qual item você deseja adicionar?",
                "confidence": 0.55,
            }

        return {
            "intent": "FALLBACK",
            "tool_calls": [],
            "message_to_user": "Desculpe, não entendi. Você pode pedir o cardápio ou informar o item desejado.",
            "confidence": 0.4,
        }
