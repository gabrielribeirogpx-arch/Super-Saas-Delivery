from __future__ import annotations

import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.customer import Customer
from app.models.menu_category import MenuCategory
from app.models.menu_item import MenuItem
from app.models.modifier_option import ModifierOption
from app.models.modifier_group import ModifierGroup
from app.models.order import Order
from app.models.tenant import Tenant
from app.models.tenant_public_settings import TenantPublicSettings
from app.services.finance import maybe_create_payment_for_order
from app.services.order_events import emit_order_created
from app.services.orders import _build_items_text, create_order_items
from app.services.product_configuration import list_modifier_groups_for_product
from app.services.tenant_resolver import TenantResolver
from utils.slug import normalize_slug

logger = logging.getLogger(__name__)
PUBLIC_TENANT_PREFIX = "[PUBLIC_TENANT]"
PUBLIC_MENU_PREFIX = "[PUBLIC_MENU]"

router = APIRouter(prefix="/public", tags=["public-menu"])


class PublicStoreResponse(BaseModel):
    id: int
    slug: str
    name: str
    custom_domain: Optional[str]
    manual_open_status: bool = True
    estimated_prep_time: Optional[str]


class PublicMenuItem(BaseModel):
    id: int
    category_id: Optional[int]
    name: str
    description: Optional[str]
    price_cents: int
    image_url: Optional[str]
    modifier_groups: list[dict] = Field(default_factory=list)


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
    tenant: PublicStoreResponse
    public_settings: Optional[PublicSettingsResponse]
    tenant_id: int
    slug: str
    categories: list[PublicMenuCategory]
    items_without_category: list[PublicMenuItem]

class PublicOrderItem(BaseModel):
    item_id: int
    quantity: int = Field(..., gt=0)


class PublicSelectedModifier(BaseModel):
    group_id: int
    option_id: int


class PublicOrderProductItem(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)
    selected_modifiers: list[PublicSelectedModifier] = Field(default_factory=list)


class PublicOrderPayload(BaseModel):
    store_id: int | None = None
    customer_name: str = ""
    customer_phone: str = ""
    address: str = ""
    notes: str = ""
    delivery_type: str = ""
    payment_method: str = ""
    payment_change_for: str = ""
    change_for: str = ""
    order_note: str = ""
    delivery_address: dict = Field(default_factory=dict)
    order_type: str = ""
    street: str = ""
    number: str = ""
    complement: str = ""
    neighborhood: str = ""
    city: str = ""
    reference: str = ""
    table_number: str = ""
    command_number: str = ""
    channel: str = ""
    items: list[PublicOrderItem] = Field(default_factory=list)
    products: list[PublicOrderProductItem] = Field(default_factory=list)

class PublicResolvedModifier(BaseModel):
    group_name: str
    option_name: str


class PublicOrderResponseItem(BaseModel):
    item_name: str
    quantity: int
    modifiers: list[PublicResolvedModifier] = Field(default_factory=list)


class PublicOrderCreateResponse(BaseModel):
    order_id: int
    status: str
    estimated_time: int
    total: float
    order_type: str
    payment_method: str | None = None
    street: str | None = None
    number: str | None = None
    complement: str | None = None
    neighborhood: str | None = None
    city: str | None = None
    reference: str | None = None
    items: list[PublicOrderResponseItem] = Field(default_factory=list)


def _resolve_estimated_time_minutes(tenant: Tenant) -> int:
    raw_value = getattr(tenant, "estimated_prep_time", None)
    if raw_value is None:
        return 30

    if isinstance(raw_value, int):
        return raw_value

    match = re.search(r"\d+", str(raw_value))
    if not match:
        return 30

    return int(match.group(0))


def _resolve_order_type(order_type: str, delivery_type: str) -> str:
    normalized = (order_type or "").strip().lower()
    if normalized in {"delivery", "pickup", "table"}:
        return normalized

    delivery = (delivery_type or "").strip().lower()
    if delivery in {"retirada", "pickup"}:
        return "pickup"
    if delivery in {"mesa", "table"}:
        return "table"
    return "delivery"



def resolve_tenant_from_host(db: Session, host: str) -> Tenant:
    normalized_host = TenantResolver.normalize_host(host)
    if normalized_host:
        tenant_by_custom_domain = (
            db.query(Tenant)
            .filter(func.lower(Tenant.custom_domain) == normalized_host)
            .first()
        )
        if tenant_by_custom_domain:
            return tenant_by_custom_domain

    return TenantResolver.resolve_from_host(db, normalized_host)


def resolve_tenant_from_slug(db: Session, slug: str) -> Tenant:
    normalized_slug = normalize_slug(slug)
    if not normalized_slug:
        raise HTTPException(status_code=400, detail="Slug inválido")

    tenant = db.query(Tenant).filter(Tenant.slug == normalized_slug).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    return tenant


def _resolve_host_from_request(request: Request) -> str:
    return request.headers.get("x-forwarded-host") or request.headers.get("host") or ""


def _resolve_base_url(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")

    if forwarded_host:
        scheme = forwarded_proto or request.url.scheme
        return f"{scheme}://{forwarded_host}"

    return str(request.base_url).rstrip("/")


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
            modifier_groups=list_modifier_groups_for_product(
                db,
                tenant_id=tenant.id,
                product_id=item.id,
                only_active_options=True,
            ),
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
        tenant=PublicStoreResponse(
            id=tenant.id,
            slug=tenant.slug,
            name=tenant.business_name,
            custom_domain=tenant.custom_domain,
            manual_open_status=(getattr(tenant, "manual_open_status", True) if getattr(tenant, "manual_open_status", None) is not None else True),
            estimated_prep_time=getattr(tenant, "estimated_prep_time", None),
        ),
        public_settings=public_settings,
        tenant_id=tenant.id,
        slug=tenant.slug,
        categories=category_payload,
        items_without_category=uncategorized,
    )


def _get_or_create_customer(db: Session, tenant_id: int, customer_name: str, customer_phone: str) -> Customer | None:
    normalized_phone = (customer_phone or "").strip()
    if not normalized_phone:
        return None

    customer = (
        db.query(Customer)
        .filter(Customer.tenant_id == tenant_id, Customer.phone == normalized_phone)
        .order_by(Customer.id.desc())
        .first()
    )
    if customer:
        normalized_name = (customer_name or "").strip()
        if normalized_name and customer.name != normalized_name:
            customer.name = normalized_name
            db.flush()
        return customer

    customer = Customer(
        tenant_id=tenant_id,
        phone=normalized_phone,
        name=(customer_name or "").strip() or "Cliente",
    )
    db.add(customer)
    db.flush()
    return customer

def _create_order_for_tenant(
    db: Session,
    tenant: Tenant,
    payload: PublicOrderPayload,
    item_modifiers_by_index: Optional[dict[int, list[PublicSelectedModifier]]] = None,
) -> PublicOrderCreateResponse:
    current_store = tenant
    if not payload.items:
        payload.items = [
            PublicOrderItem(
                item_id=entry.product_id,
                quantity=entry.quantity,
                selected_modifiers=entry.selected_modifiers,
            )
            for entry in payload.products
        ]

    if not payload.items and not payload.products:
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
    product_entries = payload.products or [
        PublicOrderProductItem(
            product_id=entry.item_id,
            quantity=entry.quantity,
            selected_modifiers=(item_modifiers_by_index or {}).get(index, []),
        )
        for index, entry in enumerate(payload.items)
    ]

    for entry in product_entries:
        menu_item = menu_item_map.get(entry.product_id)
        if not menu_item:
            raise HTTPException(status_code=400, detail=f"Item inválido: {entry.product_id}")

        selected_modifiers = entry.selected_modifiers or []
        modifier_groups = (
            db.query(ModifierGroup)
            .filter(
                ModifierGroup.tenant_id == tenant.id,
                ModifierGroup.product_id == menu_item.id,
                ModifierGroup.active.is_(True),
            )
            .all()
        )
        groups_by_id = {group.id: group for group in modifier_groups}
        options = (
            db.query(ModifierOption)
            .filter(ModifierOption.group_id.in_(groups_by_id.keys()) if groups_by_id else False)
            .all()
            if groups_by_id
            else []
        )
        option_by_id = {option.id: option for option in options}
        selected_by_group: dict[int, list[ModifierOption]] = {}
        for selected in selected_modifiers:
            group = groups_by_id.get(selected.group_id)
            option = option_by_id.get(selected.option_id)
            if not group or not option or int(option.group_id) != int(group.id) or not option.is_active:
                raise HTTPException(status_code=400, detail="Configuração de modificador inválida")
            selected_by_group.setdefault(group.id, []).append(option)

        for group in modifier_groups:
            chosen = selected_by_group.get(group.id, [])
            chosen_len = len(chosen)
            if group.required and chosen_len == 0:
                raise HTTPException(status_code=400, detail=f"Grupo obrigatório sem seleção: {group.name}")
            if chosen_len < int(group.min_selection or 0):
                raise HTTPException(status_code=400, detail=f"Mínimo não atendido para grupo: {group.name}")
            if chosen_len > int(group.max_selection or 1):
                raise HTTPException(status_code=400, detail=f"Máximo excedido para grupo: {group.name}")

        qty = int(entry.quantity)
        modifiers_payload = []
        modifiers_total_cents = 0
        for selected in selected_modifiers:
            group = groups_by_id[selected.group_id]
            option = option_by_id[selected.option_id]
            price_delta_cents = int(round(float(option.price_delta or 0) * 100))
            modifiers_payload.append(
                {
                    "group_id": selected.group_id,
                    "option_id": selected.option_id,
                    "group_name": group.name,
                    "option_name": option.name,
                    "name": option.name,
                    "price_cents": price_delta_cents,
                }
            )
            modifiers_total_cents += price_delta_cents

        subtotal = (menu_item.price_cents + modifiers_total_cents) * qty
        total_cents += subtotal
        items_structured.append(
            {
                "menu_item_id": menu_item.id,
                "name": menu_item.name,
                "quantity": qty,
                "unit_price_cents": menu_item.price_cents,
                "modifiers": modifiers_payload,
                "modifiers_total_cents": modifiers_total_cents,
                "subtotal_cents": subtotal,
            }
        )

    for entry in payload.items:
        menu_item = menu_item_map.get(entry.item_id)
        if menu_item and not any(item["menu_item_id"] == menu_item.id for item in items_structured):
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

    customer = _get_or_create_customer(
        db=db,
        tenant_id=tenant.id,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
    )

    calculated_total = total_cents
    delivery_address = payload.delivery_address or {}

    order = Order(
        tenant_id=current_store.id,
        cliente_nome=(payload.customer_name or "").strip(),
        cliente_telefone=(payload.customer_phone or "").strip(),
        itens=_build_items_text(items_structured) or "(não informado)",
        items_json=json.dumps(items_structured, ensure_ascii=False),
        endereco=(payload.address or "").strip(),
        observacao=(payload.notes or payload.order_note or "").strip(),
        tipo_entrega=(payload.delivery_type or "").upper(),
        forma_pagamento=(payload.payment_method or "").upper(),
        customer_id=(customer.id if customer else None),
        customer_name=(payload.customer_name or "").strip() or (customer.name if customer else None),
        customer_phone=(payload.customer_phone or "").strip() or (customer.phone if customer else None),
        delivery_address_json=(payload.delivery_address or None),
        payment_method=(payload.payment_method or "").strip().lower() or None,
        payment_change_for=(payload.payment_change_for or payload.change_for or None),
        order_type=_resolve_order_type(payload.order_type, payload.delivery_type),
        street=(payload.street or delivery_address.get("street") or "").strip() or None,
        number=(payload.number or delivery_address.get("number") or "").strip() or None,
        complement=(payload.complement or delivery_address.get("complement") or "").strip() or None,
        neighborhood=(payload.neighborhood or delivery_address.get("neighborhood") or delivery_address.get("district") or "").strip() or None,
        city=(payload.city or delivery_address.get("city") or "").strip() or None,
        reference=(payload.reference or delivery_address.get("reference") or "").strip() or None,
        table_number=(payload.table_number or "").strip() or None,
        command_number=(payload.command_number or "").strip() or None,
        change_for=(payload.payment_change_for or payload.change_for or None),
        channel=(payload.channel or "public_menu").strip() or None,
        order_note=(payload.order_note or payload.notes or "").strip() or None,
        status="pending",
        valor_total=calculated_total,
        total_cents=calculated_total,
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

    print("ORDER SAVED:", order.id, "STORE:", current_store.id)

    response_items = [
        PublicOrderResponseItem(
            item_name=str(entry.get("name", "") or ""),
            quantity=int(entry.get("quantity", 0) or 0),
            modifiers=[
                PublicResolvedModifier(
                    group_name=str(modifier.get("group_name", "") or "").strip(),
                    option_name=str(modifier.get("option_name", modifier.get("name", "")) or "").strip(),
                )
                for modifier in (entry.get("modifiers") or [])
                if str(modifier.get("option_name", modifier.get("name", "")) or "").strip()
            ],
        )
        for entry in items_structured
    ]

    return PublicOrderCreateResponse(
        order_id=order.id,
        status=order.status,
        estimated_time=_resolve_estimated_time_minutes(tenant),
        total=float(order.total_cents or order.valor_total or 0),
        order_type=order.order_type,
        payment_method=order.payment_method,
        street=order.street,
        number=order.number,
        complement=order.complement,
        neighborhood=order.neighborhood,
        city=order.city,
        reference=order.reference,
        items=response_items,
    )


def _get_public_tenant_by_host_payload(request: Request, db: Session) -> PublicStoreResponse:
    host = _resolve_host_from_request(request)
    tenant = getattr(request.state, "tenant", None) or resolve_tenant_from_host(db, host)
    logger.info(
        "%s resolved host=%s tenant_id=%s slug=%s",
        PUBLIC_TENANT_PREFIX,
        host,
        tenant.id,
        tenant.slug,
    )
    return PublicStoreResponse(
        id=tenant.id,
        slug=tenant.slug,
        name=tenant.business_name,
        custom_domain=tenant.custom_domain,
        manual_open_status=(getattr(tenant, "manual_open_status", True) if getattr(tenant, "manual_open_status", None) is not None else True),
        estimated_prep_time=getattr(tenant, "estimated_prep_time", None),
    )


def _get_public_menu_payload(
    request: Request,
    db: Session,
    slug: Optional[str] = None,
) -> PublicMenuResponse:
    if slug:
        tenant = resolve_tenant_from_slug(db, slug)
        logger.info(
            "%s mode=slug slug=%s tenant_id=%s",
            PUBLIC_MENU_PREFIX,
            tenant.slug,
            tenant.id,
        )
    else:
        host = _resolve_host_from_request(request)
        tenant = getattr(request.state, "tenant", None) or resolve_tenant_from_host(db, host)
        logger.info(
            "%s mode=host host=%s tenant_id=%s slug=%s",
            PUBLIC_MENU_PREFIX,
            host,
            tenant.id,
            tenant.slug,
        )

    return _build_menu_payload(db, tenant, _resolve_base_url(request))



def _coerce_to_int(value: object) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        value = value.strip()
        if value.isdigit():
            try:
                return int(value)
            except ValueError:
                return None
    return None

def _create_public_order_payload(
    request: Request,
    payload: PublicOrderPayload,
    db: Session,
    raw_payload: Optional[dict] = None,
) -> dict:
    host = _resolve_host_from_request(request)
    tenant = getattr(request.state, "tenant", None) or resolve_tenant_from_host(db, host)
    logger.info(
        "%s resolved host=%s tenant_id=%s slug=%s",
        PUBLIC_TENANT_PREFIX,
        host,
        tenant.id,
        tenant.slug,
    )
    item_modifiers_by_index: dict[int, list[PublicSelectedModifier]] = {}
    raw_items = (raw_payload or {}).get("items") if isinstance(raw_payload, dict) else None
    if isinstance(raw_items, list):
        for index, raw_item in enumerate(raw_items):
            if not isinstance(raw_item, dict):
                continue
            raw_modifiers = raw_item.get("selected_modifiers")
            if not isinstance(raw_modifiers, list):
                continue
            normalized_modifiers: list[PublicSelectedModifier] = []
            for raw_modifier in raw_modifiers:
                if not isinstance(raw_modifier, dict):
                    continue
                group_id = _coerce_to_int(raw_modifier.get("group_id"))
                option_id = _coerce_to_int(raw_modifier.get("option_id"))
                if group_id is not None and option_id is not None:
                    normalized_modifiers.append(PublicSelectedModifier(group_id=group_id, option_id=option_id))
            if normalized_modifiers:
                item_modifiers_by_index[index] = normalized_modifiers

    return _create_order_for_tenant(
        db,
        tenant,
        payload,
        item_modifiers_by_index=item_modifiers_by_index,
    )


@router.get("/tenant/by-host", response_model=PublicStoreResponse)
def get_public_tenant_by_host(request: Request, db: Session = Depends(get_db)):
    return _get_public_tenant_by_host_payload(request, db)


@router.get("/menu", response_model=PublicMenuResponse)
def get_public_menu(
    request: Request,
    slug: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    return _get_public_menu_payload(request, db, slug=slug)


@router.post("/orders", response_model=PublicOrderCreateResponse, summary="Create Public Order", operation_id="create_public_order_public_orders_post")
async def create_public_order(
    request: Request,
    payload: PublicOrderPayload,
    db: Session = Depends(get_db),
):
    raw_payload = await request.json()
    return _create_public_order_payload(request, payload, db, raw_payload=raw_payload)
