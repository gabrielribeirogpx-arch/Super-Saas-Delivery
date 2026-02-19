from __future__ import annotations

from datetime import date, datetime, time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_request_tenant_id, require_role
from app.models.admin_user import AdminUser
from app.models.inventory import (
    InventoryItem,
    InventoryMovement,
    MenuItemIngredient,
    ModifierIngredient,
)
from app.models.menu_item import MenuItem
from app.models.modifier import Modifier
from app.services.inventory import create_manual_movement

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


def _parse_datetime(value: str, is_end: bool) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed_date = date.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Data inválida") from exc
        return datetime.combine(parsed_date, time.max if is_end else time.min)


class InventoryItemBase(BaseModel):
    name: str = Field(..., min_length=1)
    unit: str = Field(..., min_length=1)
    cost_cents: int = Field(0, ge=0)
    current_stock: float = Field(0, ge=0)
    min_stock_level: float = Field(0, ge=0)
    active: bool = True


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    unit: Optional[str] = Field(None, min_length=1)
    cost_cents: Optional[int] = Field(None, ge=0)
    current_stock: Optional[float] = Field(None, ge=0)
    min_stock_level: Optional[float] = Field(None, ge=0)
    active: Optional[bool] = None


class InventoryItemRead(InventoryItemBase):
    id: int
    tenant_id: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class InventoryMovementCreate(BaseModel):
    inventory_item_id: int
    type: str
    quantity: float = Field(..., gt=0)
    reason: Optional[str] = None


class InventoryMovementRead(BaseModel):
    id: int
    tenant_id: int
    inventory_item_id: int
    item_name: str
    type: str
    quantity: float
    reason: Optional[str]
    order_id: Optional[int]
    created_at: Optional[str]


class IngredientCreate(BaseModel):
    inventory_item_id: int
    quantity: float = Field(..., gt=0)


class IngredientRead(BaseModel):
    id: int
    inventory_item_id: int
    name: str
    unit: str
    quantity: float
    created_at: Optional[str]


def _item_to_dict(item: InventoryItem) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "name": item.name,
        "unit": item.unit,
        "cost_cents": item.cost_cents,
        "current_stock": item.current_stock,
        "min_stock_level": item.min_stock_level,
        "active": item.active,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _movement_to_dict(movement: InventoryMovement) -> dict:
    item = movement.inventory_item
    return {
        "id": movement.id,
        "tenant_id": movement.tenant_id,
        "inventory_item_id": movement.inventory_item_id,
        "item_name": item.name if item else "",
        "type": movement.type,
        "quantity": movement.quantity,
        "reason": movement.reason,
        "order_id": movement.order_id,
        "created_at": movement.created_at.isoformat() if movement.created_at else None,
    }


@router.get("/items", response_model=List[InventoryItemRead])
def list_inventory_items(
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    items = (
        db.query(InventoryItem)
        .filter(InventoryItem.tenant_id == tenant_id)
        .order_by(InventoryItem.name.asc())
        .all()
    )
    return [_item_to_dict(item) for item in items]


@router.post("/items", response_model=InventoryItemRead)
def create_inventory_item(
    payload: InventoryItemCreate,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    item = InventoryItem(
        tenant_id=tenant_id,
        name=payload.name,
        unit=payload.unit,
        cost_cents=payload.cost_cents,
        current_stock=payload.current_stock,
        min_stock_level=payload.min_stock_level,
        active=payload.active,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _item_to_dict(item)


@router.patch("/items/{item_id}", response_model=InventoryItemRead)
def update_inventory_item(
    item_id: int,
    payload: InventoryItemUpdate,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.id == item_id, InventoryItem.tenant_id == tenant_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item de estoque não encontrado")

    if payload.name is not None:
        item.name = payload.name
    if payload.unit is not None:
        item.unit = payload.unit
    if payload.cost_cents is not None:
        item.cost_cents = payload.cost_cents
    if payload.current_stock is not None:
        item.current_stock = payload.current_stock
    if payload.min_stock_level is not None:
        item.min_stock_level = payload.min_stock_level
    if payload.active is not None:
        item.active = payload.active

    db.commit()
    db.refresh(item)
    return _item_to_dict(item)


@router.post("/movements", response_model=InventoryMovementRead)
def create_inventory_movement(
    payload: InventoryMovementCreate,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.id == payload.inventory_item_id,
            InventoryItem.tenant_id == tenant_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item de estoque não encontrado")

    try:
        movement = create_manual_movement(
            db,
            tenant_id=tenant_id,
            item=item,
            movement_type=payload.type,
            quantity=payload.quantity,
            reason=payload.reason,
        )
        db.commit()
        db.refresh(movement)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro ao registrar movimento") from exc

    return _movement_to_dict(movement)


@router.get("/movements", response_model=List[InventoryMovementRead])
def list_inventory_movements(
    tenant_id: int = Depends(get_request_tenant_id),
    item_id: Optional[int] = Query(None),
    de: Optional[str] = Query(None),
    para: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    query = (
        db.query(InventoryMovement)
        .join(InventoryItem, InventoryItem.id == InventoryMovement.inventory_item_id)
        .filter(InventoryMovement.tenant_id == tenant_id)
    )
    if item_id is not None:
        query = query.filter(InventoryMovement.inventory_item_id == item_id)
    if de:
        start = _parse_datetime(de, is_end=False)
        query = query.filter(InventoryMovement.created_at >= start)
    if para:
        end = _parse_datetime(para, is_end=True)
        query = query.filter(InventoryMovement.created_at <= end)

    movements = query.order_by(InventoryMovement.created_at.desc()).all()
    return [_movement_to_dict(movement) for movement in movements]


@router.get("/menu-items/{menu_item_id}/ingredients", response_model=List[IngredientRead])
def list_menu_item_ingredients(
    menu_item_id: int,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    menu_item = (
        db.query(MenuItem)
        .filter(MenuItem.id == menu_item_id, MenuItem.tenant_id == tenant_id)
        .first()
    )
    if not menu_item:
        raise HTTPException(status_code=404, detail="Item de cardápio não encontrado")

    ingredients = (
        db.query(MenuItemIngredient)
        .join(InventoryItem, InventoryItem.id == MenuItemIngredient.inventory_item_id)
        .filter(
            MenuItemIngredient.tenant_id == tenant_id,
            MenuItemIngredient.menu_item_id == menu_item.id,
        )
        .order_by(InventoryItem.name.asc())
        .all()
    )
    return [
        {
            "id": ingredient.id,
            "inventory_item_id": ingredient.inventory_item_id,
            "name": ingredient.inventory_item.name if ingredient.inventory_item else "",
            "unit": ingredient.inventory_item.unit if ingredient.inventory_item else "",
            "quantity": ingredient.quantity,
            "created_at": ingredient.created_at.isoformat() if ingredient.created_at else None,
        }
        for ingredient in ingredients
    ]


@router.post("/menu-items/{menu_item_id}/ingredients", response_model=IngredientRead)
def create_menu_item_ingredient(
    menu_item_id: int,
    payload: IngredientCreate,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    menu_item = (
        db.query(MenuItem)
        .filter(MenuItem.id == menu_item_id, MenuItem.tenant_id == tenant_id)
        .first()
    )
    if not menu_item:
        raise HTTPException(status_code=404, detail="Item de cardápio não encontrado")

    inventory_item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.id == payload.inventory_item_id,
            InventoryItem.tenant_id == tenant_id,
        )
        .first()
    )
    if not inventory_item:
        raise HTTPException(status_code=404, detail="Item de estoque não encontrado")

    ingredient = MenuItemIngredient(
        tenant_id=tenant_id,
        menu_item_id=menu_item.id,
        inventory_item_id=inventory_item.id,
        quantity=payload.quantity,
    )
    db.add(ingredient)
    db.commit()
    db.refresh(ingredient)
    return {
        "id": ingredient.id,
        "inventory_item_id": ingredient.inventory_item_id,
        "name": inventory_item.name,
        "unit": inventory_item.unit,
        "quantity": ingredient.quantity,
        "created_at": ingredient.created_at.isoformat() if ingredient.created_at else None,
    }


@router.delete("/menu-items/{menu_item_id}/ingredients")
def delete_menu_item_ingredient(
    menu_item_id: int,
    ingredient_id: int = Query(...),
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    ingredient = (
        db.query(MenuItemIngredient)
        .filter(
            MenuItemIngredient.id == ingredient_id,
            MenuItemIngredient.menu_item_id == menu_item_id,
            MenuItemIngredient.tenant_id == tenant_id,
        )
        .first()
    )
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingrediente não encontrado")
    db.delete(ingredient)
    db.commit()
    return {"ok": True}


@router.get("/modifiers/{modifier_id}/ingredients", response_model=List[IngredientRead])
def list_modifier_ingredients(
    modifier_id: int,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    modifier = (
        db.query(Modifier)
        .filter(Modifier.id == modifier_id, Modifier.tenant_id == tenant_id)
        .first()
    )
    if not modifier:
        raise HTTPException(status_code=404, detail="Adicional não encontrado")

    ingredients = (
        db.query(ModifierIngredient)
        .join(InventoryItem, InventoryItem.id == ModifierIngredient.inventory_item_id)
        .filter(
            ModifierIngredient.tenant_id == tenant_id,
            ModifierIngredient.modifier_id == modifier.id,
        )
        .order_by(InventoryItem.name.asc())
        .all()
    )
    return [
        {
            "id": ingredient.id,
            "inventory_item_id": ingredient.inventory_item_id,
            "name": ingredient.inventory_item.name if ingredient.inventory_item else "",
            "unit": ingredient.inventory_item.unit if ingredient.inventory_item else "",
            "quantity": ingredient.quantity,
            "created_at": ingredient.created_at.isoformat() if ingredient.created_at else None,
        }
        for ingredient in ingredients
    ]


@router.post("/modifiers/{modifier_id}/ingredients", response_model=IngredientRead)
def create_modifier_ingredient(
    modifier_id: int,
    payload: IngredientCreate,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    modifier = (
        db.query(Modifier)
        .filter(Modifier.id == modifier_id, Modifier.tenant_id == tenant_id)
        .first()
    )
    if not modifier:
        raise HTTPException(status_code=404, detail="Adicional não encontrado")

    inventory_item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.id == payload.inventory_item_id,
            InventoryItem.tenant_id == tenant_id,
        )
        .first()
    )
    if not inventory_item:
        raise HTTPException(status_code=404, detail="Item de estoque não encontrado")

    ingredient = ModifierIngredient(
        tenant_id=tenant_id,
        modifier_id=modifier.id,
        inventory_item_id=inventory_item.id,
        quantity=payload.quantity,
    )
    db.add(ingredient)
    db.commit()
    db.refresh(ingredient)
    return {
        "id": ingredient.id,
        "inventory_item_id": ingredient.inventory_item_id,
        "name": inventory_item.name,
        "unit": inventory_item.unit,
        "quantity": ingredient.quantity,
        "created_at": ingredient.created_at.isoformat() if ingredient.created_at else None,
    }


@router.delete("/modifiers/{modifier_id}/ingredients")
def delete_modifier_ingredient(
    modifier_id: int,
    ingredient_id: int = Query(...),
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    ingredient = (
        db.query(ModifierIngredient)
        .filter(
            ModifierIngredient.id == ingredient_id,
            ModifierIngredient.modifier_id == modifier_id,
            ModifierIngredient.tenant_id == tenant_id,
        )
        .first()
    )
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingrediente não encontrado")
    db.delete(ingredient)
    db.commit()
    return {"ok": True}
