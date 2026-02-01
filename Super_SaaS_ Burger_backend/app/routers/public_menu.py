from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.menu_category import MenuCategory
from app.models.menu_item import MenuItem
from app.models.order import Order
from app.models.tenant import Tenant
from app.models.tenant_public_settings import TenantPublicSettings
from app.services.finance import maybe_create_payment_for_order
from app.services.order_events import emit_order_created
from app.services.orders import _build_items_text, create_order_items

logger = logging.getLogger(__name__)
BASE_DOMAIN = "mandarpedido.com"
PUBLIC_TENANT_PREFIX = "[PUBLIC_TENANT]"
PUBLIC_MENU_PREFIX = "[PUBLIC_MENU]"

router = APIRouter(tags=["public-menu"])
legacy_router = APIRouter(prefix="/api/public", tags=["public-menu"])


class PublicTenantResponse(BaseModel):
    id: int
    slug: str
    name: str
    custom_domain: Optional[str]


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


class PublicSettingsResponse(BaseModel):
    cover_image_url: Optional[str]
    cover_video_url: Optional[str]
    logo_url: Optional[str]
    theme: Optional[str]
    primary_color: Optional[str]


class PublicMenuResponse(BaseModel):
    tenant: PublicTenantResponse
    public_settings: Optional[PublicSettingsResponse]
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


def _normalize_host(host: str) -> str:
    host = (host or "").split(",")[0].strip().lower()
    if ":" in host:
        host = host.split(":")[0].strip()
    return host


def resolve_tenant_from_host(db: Session, host: str) -> Tenant:
    host = _normalize_host(host)
    if not host:
        raise HTTPException(status_code=400, detail="Host ausente")

    if host.endswith(f".{BASE_DOMAIN}"):
        slug = host[: -len(f".{BASE_DOMAIN}")].strip(".")
        if not slug:
            raise HTTPException(status_code=404, detail="Tenant não encontrado")
        tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
    else:
        tenant = (
            db.query(Tenant)
            .filter(func.lower(Tenant.custom_domain) == host)
            .first()
        )

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return tenant


def _get_tenant_by_slug(db: Session, slug: str) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return tenant


def _resolve_host_from_request(request: Request) -> str:
    return request.headers.get("x-forwarded-host") or request.headers.get("host") or ""


def _resolve_image_url(base_url: str, image_url: Optional[str]) -> Optional[str]:
    if not image_url:
        return None
    if image_url.startswith("http://") or image_url.startswith("https://"):
        return image_url
    base = base_url.rstrip("/")
    if image_url.startswith("/"):
        return f"{base}{image_url}"
    return f"{base}/{image_url}"


def _build_menu_payload(
    db: Session,
    tenant: Tenant,
    base_url: str,
) -> PublicMenuResponse:
    settings = (
        db.query(TenantPublicSettings)
        .filter(TenantPublicSettings.tenant_id == tenant.id)
        .first()
    )
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
            image_url=_resolve_image_url(base_url, item.image_url),
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

    logger.info(
        "%s tenant_id=%s slug=%s categories=%s items=%s",
        PUBLIC_MENU_PREFIX,
        tenant.id,
        tenant.slug,
        len(category_payload),
        len(items),
    )

    public_settings = None
    if settings:
        public_settings = PublicSettingsResponse(
            cover_image_url=_resolve_image_url(base_url, settings.cover_image_url),
            cover_video_url=_resolve_image_url(base_url, settings.cover_video_url),
            logo_url=_resolve_image_url(base_url, settings.logo_url),
            theme=settings.theme,
            primary_color=settings.primary_color,
        )

    return PublicMenuResponse(
        tenant=PublicTenantResponse(
            id=tenant.id,
            slug=tenant.slug,
            name=tenant.business_name,
            custom_domain=tenant.custom_domain,
        ),
        public_settings=public_settings,
        tenant_id=tenant.id,
        slug=tenant.slug,
        categories=category_payload,
        items_without_category=uncategorized,
    )


def _create_order_for_tenant(
    db: Session,
    tenant: Tenant,
    payload: PublicOrderPayload,
) -> dict:
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


@router.get("/public/tenant/by-host", response_model=PublicTenantResponse)
def get_public_tenant_by_host(request: Request, db: Session = Depends(get_db)):
    host = _resolve_host_from_request(request)
    tenant = resolve_tenant_from_host(db, host)
    logger.info(
        "%s resolved host=%s tenant_id=%s slug=%s",
        PUBLIC_TENANT_PREFIX,
        host,
        tenant.id,
        tenant.slug,
    )
    return PublicTenantResponse(
        id=tenant.id,
        slug=tenant.slug,
        name=tenant.business_name,
        custom_domain=tenant.custom_domain,
    )


@router.get("/public/menu", response_model=PublicMenuResponse)
def get_public_menu(
    request: Request,
    slug: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if slug:
        tenant = _get_tenant_by_slug(db, slug)
    else:
        host = _resolve_host_from_request(request)
        tenant = resolve_tenant_from_host(db, host)
        logger.info(
            "%s resolved host=%s tenant_id=%s slug=%s",
            PUBLIC_TENANT_PREFIX,
            host,
            tenant.id,
            tenant.slug,
        )
    return _build_menu_payload(db, tenant, str(request.base_url))


@router.post("/public/orders")
def create_public_order(
    request: Request,
    payload: PublicOrderPayload,
    db: Session = Depends(get_db),
):
    host = _resolve_host_from_request(request)
    tenant = resolve_tenant_from_host(db, host)
    logger.info(
        "%s resolved host=%s tenant_id=%s slug=%s",
        PUBLIC_TENANT_PREFIX,
        host,
        tenant.id,
        tenant.slug,
    )
    return _create_order_for_tenant(db, tenant, payload)


@legacy_router.get("/{slug}/menu", response_model=PublicMenuResponse)
def get_public_menu_by_slug(slug: str, request: Request, db: Session = Depends(get_db)):
    tenant = _get_tenant_by_slug(db, slug)
    return _build_menu_payload(db, tenant, str(request.base_url))


@legacy_router.post("/{slug}/orders")
def create_public_order_by_slug(
    slug: str,
    payload: PublicOrderPayload,
    db: Session = Depends(get_db),
):
    tenant = _get_tenant_by_slug(db, slug)
    return _create_order_for_tenant(db, tenant, payload)
