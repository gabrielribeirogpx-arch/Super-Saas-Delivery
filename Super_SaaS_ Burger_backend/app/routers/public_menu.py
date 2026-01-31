from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.menu_category import MenuCategory
from app.models.menu_item import MenuItem
from app.models.order import Order
from app.models.tenant import Tenant
from app.services.finance import maybe_create_payment_for_order
from app.services.order_events import emit_order_created
from app.services.orders import _build_items_text, create_order_items

router = APIRouter(prefix="/api/public", tags=["public-menu"])


class PublicMenuItem(BaseModel):
    id: int
    category_id: Optional[int]
    name: str
    description: Optional[str]
    price_cents: int
    image_url: Optional[str]


class PublicMenuCategory(BaseModel):
    id: int
    name: str
    sort_order: int
    items: list[PublicMenuItem]


class PublicMenuResponse(BaseModel):
    tenant_id: int
    slug: str
    categories: list[PublicMenuCategory]
    items_without_category: list[PublicMenuItem]


class PublicOrderItem(BaseModel):
    item_id: int
    quantity: int = Field(..., gt=0)


class PublicOrderPayload(BaseModel):
    customer_name: str = ""
    customer_phone: str = ""
    address: str = ""
    notes: str = ""
    delivery_type: str = ""
    payment_method: str = ""
    items: list[PublicOrderItem]


def _get_tenant_by_slug(db: Session, slug: str) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return tenant


@router.get("/{slug}/menu", response_model=PublicMenuResponse)
def get_public_menu(slug: str, db: Session = Depends(get_db)):
    tenant = _get_tenant_by_slug(db, slug)

    categories = (
        db.query(MenuCategory)
        .filter(MenuCategory.tenant_id == tenant.id, MenuCategory.active.is_(True))
        .order_by(MenuCategory.sort_order.asc(), MenuCategory.name.asc())
        .all()
    )
    items = (
        db.query(MenuItem)
        .filter(MenuItem.tenant_id == tenant.id, MenuItem.active.is_(True))
        .order_by(MenuItem.name.asc())
        .all()
    )

    items_by_category: dict[int | None, list[PublicMenuItem]] = {}
    for item in items:
        entry = PublicMenuItem(
            id=item.id,
            category_id=item.category_id,
            name=item.name,
            description=item.description,
            price_cents=item.price_cents,
            image_url=item.image_url,
        )
        items_by_category.setdefault(item.category_id, []).append(entry)

    category_payload = [
        PublicMenuCategory(
            id=category.id,
            name=category.name,
            sort_order=category.sort_order,
            items=items_by_category.get(category.id, []),
        )
        for category in categories
    ]
    uncategorized = items_by_category.get(None, [])

    return PublicMenuResponse(
        tenant_id=tenant.id,
        slug=tenant.slug,
        categories=category_payload,
        items_without_category=uncategorized,
    )


@router.post("/{slug}/orders")
def create_public_order(
    slug: str,
    payload: PublicOrderPayload,
    db: Session = Depends(get_db),
):
    tenant = _get_tenant_by_slug(db, slug)
    if not payload.items:
        raise HTTPException(status_code=400, detail="Carrinho vazio")

    item_ids = [entry.item_id for entry in payload.items]
    menu_items = (
        db.query(MenuItem)
        .filter(
            MenuItem.tenant_id == tenant.id,
            MenuItem.active.is_(True),
            MenuItem.id.in_(item_ids),
        )
        .all()
    )
    menu_item_map = {item.id: item for item in menu_items}

    items_structured: list[dict] = []
    total_cents = 0
    for entry in payload.items:
        menu_item = menu_item_map.get(entry.item_id)
        if not menu_item:
            raise HTTPException(status_code=400, detail=f"Item inválido: {entry.item_id}")
        qty = int(entry.quantity)
        subtotal = menu_item.price_cents * qty
        total_cents += subtotal
        items_structured.append(
            {
                "menu_item_id": menu_item.id,
                "name": menu_item.name,
                "quantity": qty,
                "unit_price_cents": menu_item.price_cents,
                "subtotal_cents": subtotal,
            }
        )

    order = Order(
        tenant_id=tenant.id,
        cliente_nome=(payload.customer_name or "").strip(),
        cliente_telefone=(payload.customer_phone or "").strip(),
        itens=_build_items_text(items_structured) or "(não informado)",
        items_json=json.dumps(items_structured, ensure_ascii=False),
        endereco=(payload.address or "").strip(),
        observacao=(payload.notes or "").strip(),
        tipo_entrega=(payload.delivery_type or "").upper(),
        forma_pagamento=(payload.payment_method or "").upper(),
        status="RECEBIDO",
        valor_total=total_cents,
        total_cents=total_cents,
    )

    db.add(order)
    try:
        db.flush()
        create_order_items(db, tenant_id=tenant.id, order_id=order.id, items_structured=items_structured)
        maybe_create_payment_for_order(db, order, payload.payment_method)
        db.commit()
        db.refresh(order)
        emit_order_created(order)
    except Exception:
        db.rollback()
        raise

    return {"order_id": order.id, "total_cents": total_cents}
