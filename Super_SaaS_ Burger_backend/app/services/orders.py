import json
import logging
from sqlalchemy.orm import Session
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.menu_item import MenuItem
from app.models.modifier_group import ModifierGroup
from app.models.modifier_option import ModifierOption
from app.core.production import normalize_production_area
from app.models.conversation import Conversation
from app.services.finance import maybe_create_payment_for_order
from app.services.order_events import emit_order_created


logger = logging.getLogger(__name__)


def _get(d: dict, *keys, default=""):
    """Tenta várias chaves possíveis."""
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _normalize_cart_items(cart: list[dict]) -> tuple[list[dict], int]:
    items: list[dict] = []
    total_cents = 0

    for entry in cart:
        try:
            qty = int(entry.get("qty", entry.get("quantity", 0)) or 0)
        except Exception:
            qty = 0
        try:
            unit_price_cents = int(entry.get("price_cents", entry.get("unit_price_cents", 0)) or 0)
        except Exception:
            unit_price_cents = 0

        menu_item_id = entry.get("item_id", entry.get("menu_item_id"))
        name = str(entry.get("name", "") or "").strip()
        modifiers = entry.get("modifiers") or []
        normalized_modifiers: list[dict] = []
        modifiers_total_cents = 0
        if isinstance(modifiers, list):
            for modifier in modifiers:
                mod_name = str(modifier.get("name", "") or "").strip()
                mod_price = int(modifier.get("price_cents", 0) or 0)
                if mod_name:
                    normalized_modifiers.append(
                        {
                            "name": mod_name,
                            "price_cents": mod_price,
                        }
                    )
                    modifiers_total_cents += mod_price

        unit_with_modifiers = unit_price_cents + modifiers_total_cents
        subtotal_cents = unit_with_modifiers * qty

        items.append(
            {
                "menu_item_id": menu_item_id,
                "name": name,
                "quantity": qty,
                "unit_price_cents": unit_price_cents,
                "modifiers": normalized_modifiers,
                "modifiers_total_cents": modifiers_total_cents,
                "subtotal_cents": subtotal_cents,
            }
        )
        total_cents += subtotal_cents

    return items, total_cents


def _build_items_text(items: list[dict]) -> str:
    lines = []
    for entry in items:
        qty = int(entry.get("quantity", 0) or 0)
        name = entry.get("name", "") or ""
        modifiers = entry.get("modifiers") or []
        suffix = ""
        if isinstance(modifiers, list):
            names = [str(mod.get("name", "") or "").strip() for mod in modifiers if mod.get("name")]
            if names:
                suffix = f" ({', '.join(names)})"
        if qty and name:
            lines.append(f"{qty}x {name}{suffix}")
    return ", ".join(lines)


def _resolve_order_type(tipo_entrega: str) -> str:
    tipo = (tipo_entrega or "").strip().upper()
    if tipo in {"RETIRADA", "PICKUP"}:
        return "pickup"
    if tipo in {"MESA", "TABLE"}:
        return "table"
    return "delivery"




def _resolve_selected_modifiers(
    db: Session,
    tenant_id: int,
    selected_modifiers: list[dict] | None,
) -> list[dict]:
    modifiers_data: list[dict] = []
    query_filters = [ModifierGroup.tenant_id == tenant_id]
    if hasattr(ModifierOption, "tenant_id"):
        query_filters.append(getattr(ModifierOption, "tenant_id") == tenant_id)

    for selected in selected_modifiers or []:
        if isinstance(selected, dict):
            option_id = selected.get("option_id")
            group_id = selected.get("group_id")
        else:
            option_id = getattr(selected, "option_id", None)
            group_id = getattr(selected, "group_id", None)

        try:
            option_id = int(option_id)
            group_id = int(group_id)
        except (TypeError, ValueError):
            continue

        if option_id is None or group_id is None:
            continue

        option = (
            db.query(ModifierOption)
            .join(ModifierGroup, ModifierGroup.id == ModifierOption.group_id)
            .filter(
                ModifierOption.id == option_id,
                ModifierOption.group_id == group_id,
                ModifierOption.is_active == True,
                *query_filters,
            )
            .first()
        )
        if not option:
            continue
        if int(option.group_id) != int(group_id):
            continue
        option_tenant_id = getattr(option, "tenant_id", tenant_id)
        if option_tenant_id is not None and int(option_tenant_id) != int(tenant_id):
            continue

        price_delta = float(option.price_delta or 0)
        modifiers_data.append(
            {
                "group_id": option.group_id,
                "option_id": option.id,
                "name": option.name,
                "price_delta": price_delta,
                "price_cents": int(price_delta * 100),
            }
        )

    return modifiers_data

def create_order_items(
    db: Session,
    tenant_id: int,
    order_id: int,
    items_structured: list[dict],
) -> list[OrderItem]:
    def _normalize_existing_modifiers(raw_modifiers: list[dict] | None) -> list[dict]:
        normalized: list[dict] = []
        for raw_modifier in raw_modifiers or []:
            if not isinstance(raw_modifier, dict):
                continue
            try:
                group_id = int(raw_modifier.get("group_id")) if raw_modifier.get("group_id") is not None else None
                option_id = int(raw_modifier.get("option_id")) if raw_modifier.get("option_id") is not None else None
            except (TypeError, ValueError):
                group_id = None
                option_id = None

            name = str(raw_modifier.get("name") or raw_modifier.get("option_name") or "").strip()
            try:
                price_cents = int(raw_modifier.get("price_cents", 0) or 0)
            except (TypeError, ValueError):
                price_cents = 0

            try:
                price_delta = float(raw_modifier.get("price_delta")) if raw_modifier.get("price_delta") is not None else (price_cents / 100)
            except (TypeError, ValueError):
                price_delta = price_cents / 100

            if not name:
                continue

            modifier_payload = {
                "name": name,
                "price_delta": price_delta,
                "price_cents": price_cents,
            }
            group_name = str(raw_modifier.get("group_name", "") or "").strip()
            option_name = str(raw_modifier.get("option_name", "") or "").strip()
            if group_name:
                modifier_payload["group_name"] = group_name
            if option_name:
                modifier_payload["option_name"] = option_name
            if group_id is not None:
                modifier_payload["group_id"] = group_id
            if option_id is not None:
                modifier_payload["option_id"] = option_id
            normalized.append(modifier_payload)
        return normalized

    menu_item_ids = {entry.get("menu_item_id") for entry in items_structured if entry.get("menu_item_id")}
    menu_item_map: dict[int, object] = {}
    if menu_item_ids:
        rows = (
            db.query(MenuItem.id, MenuItem.production_area)
            .filter(MenuItem.tenant_id == tenant_id, MenuItem.id.in_(menu_item_ids))
            .all()
        )
        menu_item_map = {row.id: row for row in rows}

    order_items: list[OrderItem] = []
    for item in items_structured:
        menu_item = menu_item_map.get(item.get("menu_item_id"))
        selected_modifiers = item.get("selected_modifiers") or []
        logger.info(f"Selected modifiers received: {selected_modifiers}")

        resolved_modifiers = _normalize_existing_modifiers(item.get("modifiers") or [])
        if selected_modifiers:
            selected_signatures: set[tuple[int, int]] = set()
            for selected in selected_modifiers:
                if not isinstance(selected, dict):
                    continue
                try:
                    group_id = int(selected.get("group_id"))
                    option_id = int(selected.get("option_id"))
                except (TypeError, ValueError):
                    continue
                selected_signatures.add((group_id, option_id))

            resolved_from_selection = _resolve_selected_modifiers(
                db,
                tenant_id=tenant_id,
                selected_modifiers=selected_modifiers,
            )
            existing_by_signature = {
                (mod.get("group_id"), mod.get("option_id")): mod for mod in resolved_modifiers
            }
            if resolved_from_selection:
                resolved_modifiers = []
                for modifier in resolved_from_selection:
                    signature = (modifier.get("group_id"), modifier.get("option_id"))
                    enriched_modifier = dict(modifier)
                    existing_modifier = existing_by_signature.get(signature)
                    if existing_modifier:
                        if existing_modifier.get("group_name"):
                            enriched_modifier["group_name"] = existing_modifier["group_name"]
                        if existing_modifier.get("option_name"):
                            enriched_modifier["option_name"] = existing_modifier["option_name"]
                    resolved_modifiers.append(enriched_modifier)
            elif selected_signatures and resolved_modifiers:
                resolved_modifiers = [
                    mod
                    for mod in resolved_modifiers
                    if (mod.get("group_id"), mod.get("option_id")) in selected_signatures
                ]
                logger.warning(
                    "Modifier resolution returned empty; preserving payload modifiers for order_id=%s item=%s signatures=%s",
                    order_id,
                    item.get("menu_item_id"),
                    sorted(selected_signatures),
                )
            else:
                resolved_modifiers = []
            logger.info("Resolved modifiers: %s", resolved_modifiers)

        total_price_cents = int(
            item.get(
                "total_price_cents",
                item.get("subtotal_cents", 0),
            )
            or 0
        )
        order_item = OrderItem(
            tenant_id=tenant_id,
            order_id=order_id,
            menu_item_id=item.get("menu_item_id"),
            name=str(item.get("name", "") or "").strip(),
            quantity=int(item.get("quantity", 0) or 0),
            unit_price_cents=int(item.get("unit_price_cents", 0) or 0),
            subtotal_cents=total_price_cents,
            production_area=normalize_production_area(
                item.get("production_area") or getattr(menu_item, "production_area", "COZINHA")
            ),
        )
        logger.info("Resolved modifiers being saved: %s", resolved_modifiers)
        persisted_modifiers = [dict(modifier) for modifier in resolved_modifiers]
        order_item.modifiers = persisted_modifiers
        legacy_modifiers_json = [{k: v for k, v in modifier.items() if k != "price_delta"} for modifier in persisted_modifiers]
        order_item.modifiers_json = json.dumps(legacy_modifiers_json, ensure_ascii=False)
        db.add(order_item)
        order_items.append(order_item)
    return order_items


def create_order_from_conversation(
    db: Session,
    tenant_id: int,
    convo: Conversation,
    contact_name: str | None = None
) -> Order:
    """
    Cria um pedido no banco a partir do JSON convo.dados.
    Robusto: tenta várias chaves e cai em defaults.
    """
    # dados do FSM ficam aqui (JSON)
    dados = {}
    try:
        dados = json.loads(convo.dados or "{}")
        if not isinstance(dados, dict):
            dados = {}
    except Exception:
        dados = {}

    itens = _get(dados, "itens", "pedido", "order_items", default="").strip()
    tipo_entrega = _get(dados, "tipo_entrega", "modo", "entrega", default="").strip()
    endereco = _get(dados, "endereco", "endereço", "address", default="").strip()
    observacao = _get(dados, "observacao", "observação", "obs", default="").strip()
    forma_pagamento = _get(dados, "forma_pagamento", "pagamento", "payment", default="").strip()
    total_cents = _get(dados, "total_cents", "total", "valor_total", default=0)
    try:
        total_cents = int(total_cents)
    except Exception:
        total_cents = 0

    cart = dados.get("cart")
    items_structured: list[dict] = []
    if isinstance(cart, list) and cart:
        items_structured, computed_total = _normalize_cart_items(cart)
        total_cents = computed_total
        if not itens:
            itens = _build_items_text(items_structured)

    # Nome: vem do WhatsApp (contact_name). Se não tiver, tenta no JSON.
    cliente_nome = (contact_name or _get(dados, "cliente_nome", "nome", default="")).strip()

    order = Order(
        tenant_id=tenant_id,
        cliente_nome=cliente_nome or "",
        cliente_telefone=convo.telefone,

        itens=itens or "(não informado)",
        items_json=json.dumps(items_structured, ensure_ascii=False) if items_structured else "",
        endereco=endereco or "",
        observacao=observacao or "",
        tipo_entrega=(tipo_entrega or "").upper(),
        order_type=_resolve_order_type(tipo_entrega),
        forma_pagamento=(forma_pagamento or "").upper(),

        status="RECEBIDO",
        valor_total=total_cents,
        total_cents=total_cents,
    )

    db.add(order)
    try:
        db.flush()
        if items_structured:
            created_items = create_order_items(
                db,
                tenant_id=tenant_id,
                order_id=order.id,
                items_structured=items_structured,
            )
            print(
                "WHATSAPP: order_items criados",
                {"order_id": order.id, "itens": len(created_items)},
            )
        maybe_create_payment_for_order(db, order, forma_pagamento)
        db.commit()
        db.refresh(order)
        emit_order_created(order)
        return order
    except Exception:
        db.rollback()
        raise
