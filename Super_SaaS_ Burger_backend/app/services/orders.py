import json
from sqlalchemy.orm import Session
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.menu_item import MenuItem
from app.models.modifier_option import ModifierOption
from app.core.production import normalize_production_area
from app.models.conversation import Conversation
from app.services.finance import maybe_create_payment_for_order
from app.services.order_events import emit_order_created


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
    menu_item: MenuItem | None,
    selected_modifiers: list[dict] | None,
) -> list[dict]:
    _ = menu_item
    modifiers_data: list[dict] = []

    for selected in selected_modifiers or []:
        option_id = selected.get("option_id")
        group_id = selected.get("group_id")

        if option_id is None or group_id is None:
            continue

        option = db.query(ModifierOption).filter(ModifierOption.id == option_id).first()
        if not option:
            continue

        price = float(getattr(option, "price", getattr(option, "price_delta", 0)) or 0)
        modifiers_data.append(
            {
                "group_id": group_id,
                "option_id": option.id,
                "name": option.name,
                "price": price,
                "price_cents": int(price * 100),
            }
        )

    return modifiers_data

def create_order_items(
    db: Session,
    tenant_id: int,
    order_id: int,
    items_structured: list[dict],
) -> list[OrderItem]:
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
    for item_data in items_structured:
        menu_item = menu_item_map.get(item_data.get("menu_item_id"))

        modifiers_data = item_data.get("modifiers") or []
        if not modifiers_data:
            modifiers_data = []
            for selected in item_data.get("selected_modifiers", []):
                option_id = selected.get("option_id")
                group_id = selected.get("group_id")

                if option_id is None or group_id is None:
                    continue

                option = db.query(ModifierOption).filter(ModifierOption.id == option_id).first()
                if not option:
                    continue

                price = float(getattr(option, "price", getattr(option, "price_delta", 0)) or 0)
                modifiers_data.append(
                    {
                        "group_id": group_id,
                        "option_id": option.id,
                        "name": option.name,
                        "price": price,
                        "price_cents": int(price * 100),
                    }
                )

        total_price_cents = int(
            item_data.get(
                "total_price_cents",
                item_data.get("subtotal_cents", 0),
            )
            or 0
        )
        order_item = OrderItem(
            tenant_id=tenant_id,
            order_id=order_id,
            menu_item_id=item_data.get("menu_item_id"),
            name=str(item_data.get("name", "") or "").strip(),
            quantity=int(item_data.get("quantity", 0) or 0),
            unit_price_cents=int(item_data.get("unit_price_cents", 0) or 0),
            subtotal_cents=total_price_cents,
            production_area=normalize_production_area(
                item_data.get("production_area") or getattr(menu_item, "production_area", "COZINHA")
            ),
        )
        order_item.modifiers = modifiers_data
        order_item.modifiers_json = json.dumps(modifiers_data, ensure_ascii=False)
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
