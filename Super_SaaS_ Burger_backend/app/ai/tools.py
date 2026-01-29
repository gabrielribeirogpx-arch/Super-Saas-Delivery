from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.menu_item import MenuItem
from app.models.modifier import Modifier
from app.models.order import Order
from app.services.menu_search import normalize, search_menu_items
from app.services.orders import create_order_items


ACTIVE_ORDER_STATUSES = {"RECEBIDO", "EM_PREPARO", "PREPARO"}


def _safe_json_load(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            return []
    return []


def _build_items_text(items: list[dict[str, Any]]) -> str:
    lines = []
    for entry in items:
        qty = int(entry.get("quantity", 0) or 0)
        name = str(entry.get("name", "") or "").strip()
        modifiers = entry.get("modifiers") or []
        suffix = ""
        if isinstance(modifiers, list):
            names = [str(mod.get("name", "") or "").strip() for mod in modifiers if mod.get("name")]
            if names:
                suffix = f" ({', '.join(names)})"
        if qty and name:
            lines.append(f"{qty}x {name}{suffix}")
    return ", ".join(lines) if lines else "(em aberto)"


def _format_brl(cents: int) -> str:
    value = (int(cents or 0)) / 100
    formatted = f"{value:,.2f}"
    return f"R$ {formatted}".replace(",", "X").replace(".", ",").replace("X", ".")


def _resolve_modifiers(db: Session, tenant_id: int, modifiers: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not modifiers:
        return []
    modifier_names = []
    for entry in modifiers:
        if isinstance(entry, dict):
            name = str(entry.get("name") or "").strip()
        else:
            name = str(entry or "").strip()
        if name:
            modifier_names.append(name)

    if not modifier_names:
        return []

    normalized_names = {normalize(name): name for name in modifier_names if normalize(name)}
    if not normalized_names:
        return []

    candidates = (
        db.query(Modifier)
        .filter(Modifier.tenant_id == tenant_id, Modifier.active.is_(True))
        .all()
    )
    resolved: list[dict[str, Any]] = []
    for candidate in candidates:
        normalized = normalize(candidate.name)
        if normalized in normalized_names:
            resolved.append({"name": candidate.name, "price_cents": int(candidate.price_cents or 0)})
    return resolved


def ensure_open_order(db: Session, tenant_id: int, phone: str) -> Order:
    order = (
        db.query(Order)
        .filter(
            Order.tenant_id == tenant_id,
            Order.cliente_telefone == phone,
            Order.status.in_(ACTIVE_ORDER_STATUSES),
        )
        .order_by(Order.created_at.desc())
        .first()
    )
    if order:
        return order

    order = Order(
        tenant_id=tenant_id,
        cliente_nome="",
        cliente_telefone=phone,
        itens="(em aberto)",
        items_json="[]",
        endereco="",
        observacao="",
        tipo_entrega="",
        forma_pagamento="",
        valor_total=0,
        total_cents=0,
        status="RECEBIDO",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def add_item(
    db: Session,
    tenant_id: int,
    phone: str,
    item_id: int | None = None,
    item_name: str | None = None,
    qty: int | None = None,
    modifiers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    order = ensure_open_order(db, tenant_id, phone)

    menu_item = None
    if item_id:
        menu_item = (
            db.query(MenuItem)
            .filter(MenuItem.tenant_id == tenant_id, MenuItem.id == item_id, MenuItem.active.is_(True))
            .first()
        )
    if not menu_item and item_name:
        matches = search_menu_items(db, tenant_id, item_name, limit=1)
        if matches:
            menu_item, score = matches[0]
            if score < 0.6:
                menu_item = None

    if not menu_item:
        return {
            "ok": False,
            "message": "Não encontrei esse item no cardápio. Quer ver o menu?",
        }

    quantity = max(int(qty or 1), 1)
    resolved_modifiers = _resolve_modifiers(db, tenant_id, modifiers)
    modifiers_total_cents = sum(int(mod.get("price_cents", 0) or 0) for mod in resolved_modifiers)

    item_entry = {
        "menu_item_id": menu_item.id,
        "name": menu_item.name,
        "quantity": quantity,
        "unit_price_cents": int(menu_item.price_cents or 0),
        "modifiers": resolved_modifiers,
        "modifiers_total_cents": modifiers_total_cents,
        "subtotal_cents": (int(menu_item.price_cents or 0) + modifiers_total_cents) * quantity,
    }

    items_json = _safe_json_load(order.items_json)
    items_json.append(item_entry)
    order.items_json = json.dumps(items_json, ensure_ascii=False)
    order.itens = _build_items_text(items_json)
    total_cents = sum(int(entry.get("subtotal_cents", 0) or 0) for entry in items_json)
    order.total_cents = total_cents
    order.valor_total = total_cents

    create_order_items(db, tenant_id=tenant_id, order_id=order.id, items_structured=[item_entry])
    db.commit()

    return {
        "ok": True,
        "order_id": order.id,
        "message": f"Adicionei {quantity}x {menu_item.name} ao seu pedido.",
    }


def list_menu(db: Session, tenant_id: int, limit: int = 10) -> dict[str, Any]:
    items = (
        db.query(MenuItem)
        .filter(MenuItem.tenant_id == tenant_id, MenuItem.active.is_(True))
        .order_by(MenuItem.id.asc())
        .limit(limit)
        .all()
    )
    if not items:
        return {"ok": False, "message": "Ainda não temos itens cadastrados no cardápio."}

    lines = [f"{item.name} — {_format_brl(item.price_cents)}" for item in items]
    return {"ok": True, "message": "\n".join(lines)}


def checkout(db: Session, tenant_id: int, phone: str, order_id: int | None = None) -> dict[str, Any]:
    order = None
    if order_id:
        order = (
            db.query(Order)
            .filter(Order.tenant_id == tenant_id, Order.id == order_id)
            .first()
        )
    if not order:
        order = ensure_open_order(db, tenant_id, phone)

    items = _safe_json_load(order.items_json)
    if not items:
        return {
            "ok": False,
            "message": "Seu pedido ainda está vazio. Quer ver o cardápio?",
        }

    total_cents = sum(int(entry.get("subtotal_cents", 0) or 0) for entry in items)
    order.total_cents = total_cents
    order.valor_total = total_cents
    order.itens = _build_items_text(items)
    db.commit()

    return {
        "ok": True,
        "order_id": order.id,
        "message": f"Pedido registrado com {len(items)} itens. Total {_format_brl(total_cents)}. Informe endereço e forma de pagamento.",
    }


def order_status(db: Session, tenant_id: int, phone: str) -> dict[str, Any]:
    order = (
        db.query(Order)
        .filter(Order.tenant_id == tenant_id, Order.cliente_telefone == phone)
        .order_by(Order.created_at.desc())
        .first()
    )
    if not order:
        return {"ok": False, "message": "Não encontrei pedidos recentes para este número."}

    status = (order.status or "").upper()
    return {"ok": True, "order_id": order.id, "message": f"Seu pedido #{order.id} está com status {status}."}
