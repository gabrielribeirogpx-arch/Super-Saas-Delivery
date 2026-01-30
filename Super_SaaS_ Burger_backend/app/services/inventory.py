import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models.inventory import (
    InventoryItem,
    InventoryMovement,
    MenuItemIngredient,
    ModifierIngredient,
)
from app.models.menu_item import MenuItem
from app.models.modifier import Modifier
from app.models.order import Order
from app.models.order_item import OrderItem


def _parse_modifiers(value: str | None) -> list[dict]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _safe_items_json(value: str | None) -> list[dict]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _find_menu_item(
    db: Session,
    tenant_id: int,
    menu_item_id: int | None,
    name: str | None,
) -> Optional[MenuItem]:
    if menu_item_id:
        item = (
            db.query(MenuItem)
            .filter(MenuItem.id == menu_item_id, MenuItem.tenant_id == tenant_id)
            .first()
        )
        if item:
            return item
    if name:
        return (
            db.query(MenuItem)
            .filter(MenuItem.tenant_id == tenant_id, MenuItem.name == name)
            .first()
        )
    return None


def _find_modifier(
    db: Session,
    tenant_id: int,
    modifier_id: int | None,
    name: str | None,
) -> Optional[Modifier]:
    if modifier_id:
        modifier = (
            db.query(Modifier)
            .filter(Modifier.id == modifier_id, Modifier.tenant_id == tenant_id)
            .first()
        )
        if modifier:
            return modifier
    if name:
        return (
            db.query(Modifier)
            .filter(Modifier.tenant_id == tenant_id, Modifier.name == name)
            .first()
        )
    return None


def _apply_movement(
    db: Session,
    item: InventoryItem,
    movement_type: str,
    quantity: float,
    reason: str | None,
    order_id: int | None,
) -> InventoryMovement:
    movement = InventoryMovement(
        tenant_id=item.tenant_id,
        inventory_item_id=item.id,
        type=movement_type,
        quantity=quantity,
        reason=reason,
        order_id=order_id,
    )
    db.add(movement)
    if movement_type == "IN":
        item.current_stock += quantity
    elif movement_type == "OUT":
        item.current_stock -= quantity
    elif movement_type == "ADJUST":
        item.current_stock = quantity
    return movement


def create_manual_movement(
    db: Session,
    tenant_id: int,
    item: InventoryItem,
    movement_type: str,
    quantity: float,
    reason: str | None,
) -> InventoryMovement:
    movement_type = movement_type.upper()
    if movement_type not in {"IN", "OUT", "ADJUST"}:
        raise ValueError("Tipo de movimento inválido")
    if quantity <= 0:
        raise ValueError("Quantidade deve ser maior que zero")
    if movement_type == "ADJUST" and not reason:
        raise ValueError("Motivo é obrigatório para ajuste")
    return _apply_movement(db, item, movement_type, quantity, reason, order_id=None)


def _ensure_order_items(db: Session, order: Order) -> list[dict]:
    items = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order.id, OrderItem.tenant_id == order.tenant_id)
        .order_by(OrderItem.id.asc())
        .all()
    )
    if items:
        normalized: list[dict] = []
        for item in items:
            normalized.append(
                {
                    "menu_item_id": item.menu_item_id,
                    "name": item.name,
                    "quantity": item.quantity,
                    "modifiers": _parse_modifiers(item.modifiers_json),
                }
            )
        return normalized
    return _safe_items_json(order.items_json)


def apply_stock_for_order(db: Session, order: Order) -> bool:
    existing = (
        db.query(InventoryMovement)
        .filter(
            InventoryMovement.tenant_id == order.tenant_id,
            InventoryMovement.order_id == order.id,
            InventoryMovement.type == "OUT",
            InventoryMovement.reason == "sale",
        )
        .first()
    )
    if existing:
        return False

    items_structured = _ensure_order_items(db, order)
    if not items_structured:
        return False

    for entry in items_structured:
        quantity = float(
            entry.get("quantity", entry.get("qtd", entry.get("qty", 0))) or 0
        )
        if quantity <= 0:
            continue
        menu_item = _find_menu_item(
            db,
            tenant_id=order.tenant_id,
            menu_item_id=entry.get("menu_item_id", entry.get("item_id")),
            name=str(entry.get("name", "") or "").strip(),
        )
        if menu_item:
            ingredients = (
                db.query(MenuItemIngredient)
                .filter(
                    MenuItemIngredient.tenant_id == order.tenant_id,
                    MenuItemIngredient.menu_item_id == menu_item.id,
                )
                .all()
            )
            for ingredient in ingredients:
                item_qty = float(ingredient.quantity or 0)
                if item_qty <= 0:
                    continue
                item = ingredient.inventory_item
                if not item:
                    item = (
                        db.query(InventoryItem)
                        .filter(
                            InventoryItem.id == ingredient.inventory_item_id,
                            InventoryItem.tenant_id == order.tenant_id,
                        )
                        .first()
                    )
                if not item:
                    continue
                _apply_movement(
                    db,
                    item=item,
                    movement_type="OUT",
                    quantity=item_qty * quantity,
                    reason="sale",
                    order_id=order.id,
                )

        modifiers = entry.get("modifiers") or []
        if isinstance(modifiers, list):
            for modifier_entry in modifiers:
                modifier = _find_modifier(
                    db,
                    tenant_id=order.tenant_id,
                    modifier_id=modifier_entry.get("id"),
                    name=str(modifier_entry.get("name", "") or "").strip(),
                )
                if not modifier:
                    continue
                ingredients = (
                    db.query(ModifierIngredient)
                    .filter(
                        ModifierIngredient.tenant_id == order.tenant_id,
                        ModifierIngredient.modifier_id == modifier.id,
                    )
                    .all()
                )
                for ingredient in ingredients:
                    item_qty = float(ingredient.quantity or 0)
                    if item_qty <= 0:
                        continue
                    item = ingredient.inventory_item
                    if not item:
                        item = (
                            db.query(InventoryItem)
                            .filter(
                                InventoryItem.id == ingredient.inventory_item_id,
                                InventoryItem.tenant_id == order.tenant_id,
                            )
                            .first()
                        )
                    if not item:
                        continue
                    _apply_movement(
                        db,
                        item=item,
                        movement_type="OUT",
                        quantity=item_qty * quantity,
                        reason="sale",
                        order_id=order.id,
                    )

    return True


def count_low_stock(db: Session, tenant_id: int) -> int:
    return (
        db.query(InventoryItem)
        .filter(
            InventoryItem.tenant_id == tenant_id,
            InventoryItem.active.is_(True),
            InventoryItem.current_stock < InventoryItem.min_stock_level,
        )
        .count()
    )
