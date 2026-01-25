from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.models.menu_item import MenuItem

router = APIRouter(prefix="/api", tags=["menu"])


class MenuItemOut(BaseModel):
    id: int
    tenant_id: int
    name: str
    price_cents: int
    active: bool
    created_at: Optional[str] = None


class MenuItemCreate(BaseModel):
    name: str = Field(..., min_length=1)
    price_cents: int = Field(..., ge=0)
    active: bool = True


class MenuItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    price_cents: Optional[int] = Field(None, ge=0)
    active: Optional[bool] = None


class MenuItemActive(BaseModel):
    active: bool


def _menu_item_to_dict(item: MenuItem) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "name": item.name,
        "price_cents": item.price_cents,
        "active": item.active,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.get("/menu/{tenant_id}", response_model=List[MenuItemOut])
def list_menu_items(tenant_id: int, db: Session = Depends(get_db)):
    items = (
        db.query(MenuItem)
        .filter(MenuItem.tenant_id == tenant_id)
        .order_by(MenuItem.id.asc())
        .all()
    )
    return [_menu_item_to_dict(item) for item in items]


@router.post("/menu/{tenant_id}", response_model=MenuItemOut)
def create_menu_item(tenant_id: int, payload: MenuItemCreate, db: Session = Depends(get_db)):
    item = MenuItem(
        tenant_id=tenant_id,
        name=payload.name,
        price_cents=payload.price_cents,
        active=payload.active,
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

    existing = db.query(MenuItem).filter(MenuItem.tenant_id == tenant_id).count()
    if existing:
        items = (
            db.query(MenuItem)
            .filter(MenuItem.tenant_id == tenant_id)
            .order_by(MenuItem.id.asc())
            .all()
        )
        return [_menu_item_to_dict(item) for item in items]

    samples = [
        ("Burger Clássico", 2500),
        ("Cheeseburger Duplo", 3200),
        ("Batata Frita", 1400),
        ("Refrigerante Lata", 900),
    ]
    created_items: List[MenuItem] = []
    for name, price_cents in samples:
        item = MenuItem(
            tenant_id=tenant_id,
            name=name,
            price_cents=price_cents,
            active=True,
        )
        db.add(item)
        created_items.append(item)

    db.commit()
    for item in created_items:
        db.refresh(item)
    return [_menu_item_to_dict(item) for item in created_items]
