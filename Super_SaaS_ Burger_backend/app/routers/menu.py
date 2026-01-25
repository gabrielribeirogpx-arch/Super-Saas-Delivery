from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.sql import nullslast
from typing import List, Optional

from app.core.database import get_db
from app.models.menu_item import MenuItem
from app.models.menu_category import MenuCategory

router = APIRouter(prefix="/api", tags=["menu"])


class MenuItemOut(BaseModel):
    id: int
    tenant_id: int
    category_id: Optional[int] = None
    name: str
    price_cents: int
    active: bool
    created_at: Optional[str] = None


class MenuItemCreate(BaseModel):
    name: str = Field(..., min_length=1)
    price_cents: int = Field(..., ge=0)
    active: bool = True
    category_id: Optional[int] = None


class MenuItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    price_cents: Optional[int] = Field(None, ge=0)
    active: Optional[bool] = None
    category_id: Optional[int] = None


class MenuItemActive(BaseModel):
    active: bool


def _menu_item_to_dict(item: MenuItem) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "category_id": item.category_id,
        "name": item.name,
        "price_cents": item.price_cents,
        "active": item.active,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }

def _validate_category_id(db: Session, tenant_id: int, category_id: Optional[int]) -> None:
    if category_id is None:
        return
    category = (
        db.query(MenuCategory)
        .filter(MenuCategory.id == category_id, MenuCategory.tenant_id == tenant_id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=400, detail="Categoria inválida para o tenant")

def _build_menu_query(
    db: Session,
    tenant_id: int,
    category_id: Optional[int],
):
    query = db.query(MenuItem).filter(MenuItem.tenant_id == tenant_id)
    if category_id is not None:
        query = query.filter(MenuItem.category_id == category_id)
    return query.order_by(nullslast(MenuItem.category_id), MenuItem.name.asc())


@router.get("/menu/{tenant_id}", response_model=List[MenuItemOut])
def list_menu_items(tenant_id: int, db: Session = Depends(get_db)):
    items = _build_menu_query(db, tenant_id, None).all()
    return [_menu_item_to_dict(item) for item in items]

@router.get("/menu", response_model=List[MenuItemOut])
def list_menu_items_query(
    tenant_id: int = Query(...),
    category_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    items = _build_menu_query(db, tenant_id, category_id).all()
    return [_menu_item_to_dict(item) for item in items]


@router.post("/menu/{tenant_id}", response_model=MenuItemOut)
def create_menu_item(tenant_id: int, payload: MenuItemCreate, db: Session = Depends(get_db)):
    _validate_category_id(db, tenant_id, payload.category_id)
    item = MenuItem(
        tenant_id=tenant_id,
        name=payload.name,
        price_cents=payload.price_cents,
        active=payload.active,
        category_id=payload.category_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _menu_item_to_dict(item)


@router.put("/menu/{tenant_id}/{item_id}", response_model=MenuItemOut)
def update_menu_item(
    tenant_id: int,
    item_id: int,
    payload: MenuItemUpdate,
    db: Session = Depends(get_db),
):
    item = (
        db.query(MenuItem)
        .filter(MenuItem.tenant_id == tenant_id, MenuItem.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item do cardápio não encontrado")

    if payload.name is not None:
        item.name = payload.name
    if payload.price_cents is not None:
        item.price_cents = payload.price_cents
    if payload.active is not None:
        item.active = payload.active
    if payload.category_id is not None:
        _validate_category_id(db, tenant_id, payload.category_id)
        item.category_id = payload.category_id

    db.commit()
    db.refresh(item)
    return _menu_item_to_dict(item)


@router.patch("/menu/{tenant_id}/{item_id}/active", response_model=MenuItemOut)
def toggle_menu_item(
    tenant_id: int,
    item_id: int,
    payload: MenuItemActive,
    db: Session = Depends(get_db),
):
    item = (
        db.query(MenuItem)
        .filter(MenuItem.tenant_id == tenant_id, MenuItem.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item do cardápio não encontrado")
    item.active = payload.active
    db.commit()
    db.refresh(item)
    return _menu_item_to_dict(item)


@router.post("/menu/{tenant_id}/seed", response_model=List[MenuItemOut])
def seed_menu(tenant_id: int, db: Session = Depends(get_db)):
    if tenant_id != 1:
        raise HTTPException(status_code=400, detail="Seed disponível apenas para tenant 1")

    categories_seed = [
        ("Lanches", 1),
        ("Bebidas", 2),
        ("Acompanhamentos", 3),
    ]
    categories_map = {}
    for name, position in categories_seed:
        category = (
            db.query(MenuCategory)
            .filter(MenuCategory.tenant_id == tenant_id, MenuCategory.name == name)
            .first()
        )
        if not category:
            category = MenuCategory(
                tenant_id=tenant_id,
                name=name,
                position=position,
                active=True,
            )
            db.add(category)
        else:
            category.position = position
            category.active = True
        categories_map[name] = category

    db.flush()

    items_seed = [
        ("Burger Clássico", 2500, "Lanches"),
        ("Cheeseburger Duplo", 3200, "Lanches"),
        ("Batata Frita", 1400, "Acompanhamentos"),
        ("Refrigerante Lata", 900, "Bebidas"),
    ]
    for name, price_cents, category_name in items_seed:
        category = categories_map.get(category_name)
        item = (
            db.query(MenuItem)
            .filter(MenuItem.tenant_id == tenant_id, MenuItem.name == name)
            .first()
        )
        if not item:
            item = MenuItem(
                tenant_id=tenant_id,
                name=name,
                price_cents=price_cents,
                active=True,
                category_id=category.id if category else None,
            )
            db.add(item)
        else:
            item.price_cents = price_cents
            item.active = True
            if category:
                item.category_id = category.id

    db.commit()
    items = _build_menu_query(db, tenant_id, None).all()
    return [_menu_item_to_dict(item) for item in items]
