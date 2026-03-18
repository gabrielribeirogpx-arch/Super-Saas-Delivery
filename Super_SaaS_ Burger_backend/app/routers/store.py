from __future__ import annotations

from typing import Any
from decimal import Decimal
from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, inspect
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.coupon import Coupon
from app.models.customer import Customer
from app.models.customer_address import CustomerAddress
from app.models.customer_benefit import CustomerBenefit
from app.models.customer_points import CustomerPoints
from app.models.customer_tag import CustomerTag
from app.models.customer_stats import CustomerStats
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.tenant import Tenant
from app.routers.public_menu import PublicOrderCreateResponse, PublicOrderPayload, _create_order_for_tenant
from app.services.geocoding_service import lookup_cep
from app.services.tenant_resolver import TenantResolver

router = APIRouter(tags=["store"])


class StoreCustomerLookupResponse(BaseModel):
    found: bool
    exists: bool
    name: str | None
    customer_id: int | None = None
    address: dict[str, Any] | None
    customer: dict[str, Any] | None = None


class CustomerAddressRead(BaseModel):
    id: int
    cep: str
    street: str
    number: str
    complement: str | None
    neighborhood: str
    city: str
    state: str | None


class StoreCustomerAddressesResponse(BaseModel):
    found: bool
    customer: dict[str, Any] | None
    addresses: list[dict[str, Any]]


class CustomerBenefitRead(BaseModel):
    type: str
    title: str
    description: str | None = None
    value: float | None = None
    metadata: dict[str, Any] | None = None


class StoreCustomerBenefitsResponse(BaseModel):
    found: bool
    customer: dict[str, Any] | None
    benefits: list[CustomerBenefitRead]


class CustomerProfileAddressRead(BaseModel):
    id: int
    zip: str
    street: str
    number: str
    complement: str | None
    neighborhood: str
    city: str
    state: str | None
    is_default: bool


class StoreCustomerPointsRead(BaseModel):
    available: int
    lifetime: int


class StoreCustomerActiveBenefitRead(BaseModel):
    id: int
    type: str
    value: float
    coupon_code: str | None = None


class StoreCustomerStatsRead(BaseModel):
    total_orders: int
    total_spent: float


class StoreCustomerProfileRead(BaseModel):
    id: int
    name: str
    phone: str
    email: str | None
    addresses: list[CustomerProfileAddressRead]
    points: StoreCustomerPointsRead | None
    active_benefits: list[StoreCustomerActiveBenefitRead]
    tags: list[str]
    stats: StoreCustomerStatsRead | None


class StoreCustomerProfileResponse(BaseModel):
    found: bool
    customer: StoreCustomerProfileRead | None


class CustomerProfileResponse(BaseModel):
    id: int
    name: str
    phone: str
    email: str | None
    addresses: list[CustomerAddressRead]


class CustomerProfileUpdatePayload(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None


class CustomerOrdersResponseItem(BaseModel):
    id: int
    order_number: int | None
    date: datetime | None
    items: list[str]
    total: int


class CustomerDiscountsResponse(BaseModel):
    is_vip: bool


def _table_exists(db: Session, table_name: str) -> bool:
    try:
        bind = db.get_bind()
        if bind is None:
            return False
        return inspect(bind).has_table(table_name)
    except Exception:
        return False


class ValidateCouponPayload(BaseModel):
    code: str
    order_total: float
    customer_id: int | None = None


class ValidateCouponResponse(BaseModel):
    valid: bool
    discount_amount: float
    new_total: float
    message: str


class CepLookupResponse(BaseModel):
    zip: str
    street: str
    neighborhood: str
    city: str
    state: str


def _resolve_tenant_id(request: Request) -> int:
    tenant = getattr(request.state, "tenant", None)
    if tenant is not None and getattr(tenant, "id", None) is not None:
        return int(tenant.id)

    tenant_id = TenantResolver.resolve_tenant_id_from_request(request)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Tenant não identificado")
    return int(tenant_id)


def _normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def _address_payload(address: CustomerAddress | None) -> dict[str, Any] | None:
    if not address:
        return None

    return {
        "cep": address.cep,
        "street": address.street,
        "number": address.number,
        "complement": address.complement,
        "neighborhood": address.neighborhood,
        "city": address.city,
        "state": address.state,
        "district": address.neighborhood,
        "zip": address.cep,
    }


def _is_vip_customer(db: Session, tenant_id: int, customer_id: int) -> bool:
    customer = (
        db.query(Customer.id)
        .filter(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        .first()
    )
    if not customer:
        return False

    total_orders, total_spent = (
        db.query(
            func.count(Order.id),
            func.coalesce(func.sum(func.coalesce(Order.total_cents, Order.valor_total)), 0),
        )
        .filter(Order.tenant_id == tenant_id, Order.customer_id == customer_id)
        .one()
    )
    return bool(int(total_spent or 0) >= 500 or int(total_orders or 0) >= 10)


def _get_customer_or_404(db: Session, tenant_id: int, customer_id: int) -> Customer:
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.tenant_id == tenant_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return customer


def _get_customer_by_phone(db: Session, tenant_id: int, phone: str) -> Customer | None:
    normalized_phone = _normalize_phone(phone)
    if not normalized_phone:
        return None

    return (
        db.query(Customer)
        .filter(Customer.tenant_id == tenant_id, Customer.phone == normalized_phone)
        .order_by(Customer.id.desc())
        .first()
    )


@router.get("/customer-by-phone", response_model=StoreCustomerLookupResponse)
def get_store_customer_by_phone(
    request: Request,
    phone: str = Query(..., min_length=3),
    db: Session = Depends(get_db),
):
    tenant_id = _resolve_tenant_id(request)
    customer = _get_customer_by_phone(db=db, tenant_id=tenant_id, phone=phone)
    if not customer:
        return StoreCustomerLookupResponse(found=False, exists=False, name=None, address=None)

    if customer:
        latest_address = (
            db.query(CustomerAddress)
            .filter(CustomerAddress.customer_id == customer.id)
            .order_by(CustomerAddress.id.desc())
            .first()
        )
        address_payload = _address_payload(latest_address)
        return StoreCustomerLookupResponse(
            found=True,
            exists=True,
            name=customer.name,
            customer_id=customer.id,
            address=address_payload,
            customer={
                "id": customer.id,
                "name": customer.name,
                "phone": customer.phone,
                "email": customer.email,
                "address": address_payload,
            },
        )

    return StoreCustomerLookupResponse(
        found=False,
        exists=False,
        name=None,
        customer_id=None,
        address=None,
        customer=None,
    )


@router.get("/customer-addresses", response_model=StoreCustomerAddressesResponse)
def get_store_customer_addresses(
    request: Request,
    phone: str = Query(..., min_length=3),
    db: Session = Depends(get_db),
):
    try:
        tenant_id = _resolve_tenant_id(request)
        customer = _get_customer_by_phone(db=db, tenant_id=tenant_id, phone=phone)
        if not customer:
            return StoreCustomerAddressesResponse(found=False, customer=None, addresses=[])

        addresses = (
            db.query(CustomerAddress)
            .filter(CustomerAddress.customer_id == customer.id)
            .order_by(CustomerAddress.id.desc())
            .all()
        )

        return StoreCustomerAddressesResponse(
            found=True,
            customer={"id": customer.id, "name": customer.name, "phone": customer.phone},
            addresses=[({"id": address.id} | (_address_payload(address) or {})) for address in addresses],
        )
    except Exception:
        return StoreCustomerAddressesResponse(found=False, customer=None, addresses=[])


@router.get("/customer-benefits", response_model=StoreCustomerBenefitsResponse)
def get_store_customer_benefits(
    request: Request,
    phone: str = Query(..., min_length=3),
    db: Session = Depends(get_db),
):
    try:
        tenant_id = _resolve_tenant_id(request)
        customer = _get_customer_by_phone(db=db, tenant_id=tenant_id, phone=phone)
        if not customer:
            return StoreCustomerBenefitsResponse(found=False, customer=None, benefits=[])

        benefits: list[CustomerBenefitRead] = []
        rows = (
            db.query(CustomerBenefit)
            .filter(
                CustomerBenefit.tenant_id == tenant_id,
                CustomerBenefit.customer_id == customer.id,
                CustomerBenefit.active.is_(True),
            )
            .order_by(CustomerBenefit.id.desc())
            .all()
        )
        for benefit in rows:
            benefits.append(
                CustomerBenefitRead(
                    type=benefit.benefit_type,
                    title=benefit.title,
                    description=benefit.description,
                    value=float(benefit.benefit_value) if benefit.benefit_value is not None else None,
                    metadata={"code": benefit.coupon_code} if benefit.coupon_code else None,
                )
            )

        if _is_vip_customer(db=db, tenant_id=tenant_id, customer_id=customer.id):
            benefits.append(
                CustomerBenefitRead(
                    type="vip",
                    title="Cliente VIP",
                    description="Benefícios exclusivos para clientes recorrentes",
                )
            )

        try:
            points_row = (
                db.query(CustomerPoints)
                .filter(CustomerPoints.tenant_id == tenant_id, CustomerPoints.customer_id == customer.id)
                .first()
            )
            if points_row and int(points_row.available_points or 0) > 0:
                benefits.append(
                    CustomerBenefitRead(
                        type="loyalty_points",
                        title="Pontos disponíveis",
                        description=f"Você possui {int(points_row.available_points)} pontos para trocar.",
                        value=float(points_row.available_points),
                    )
                )
        except Exception:
            points_row = None

        tags = (
            db.query(CustomerTag)
            .filter(CustomerTag.tenant_id == tenant_id, CustomerTag.customer_id == customer.id)
            .all()
        )
        for tag in tags:
            benefits.append(
                CustomerBenefitRead(
                    type="customer_tag",
                    title=tag.tag,
                    description=tag.description,
                )
            )

        return StoreCustomerBenefitsResponse(
            found=True,
            customer={"id": customer.id, "name": customer.name, "phone": customer.phone},
            benefits=benefits,
        )
    except Exception:
        return StoreCustomerBenefitsResponse(found=False, customer=None, benefits=[])


@router.get("/customer-profile", response_model=StoreCustomerProfileResponse)
def get_store_customer_profile(
    request: Request,
    phone: str = Query(..., min_length=3),
    db: Session = Depends(get_db),
):
    tenant_id = _resolve_tenant_id(request)
    normalized_phone = _normalize_phone(phone)
    if not normalized_phone:
        return StoreCustomerProfileResponse(found=False, customer=None)

    benefits_table_exists = _table_exists(db, "customer_benefits")
    customer_query = db.query(Customer).options(
        selectinload(Customer.addresses),
        selectinload(Customer.tags),
    )
    if benefits_table_exists:
        customer_query = customer_query.options(selectinload(Customer.benefits))

    customer = (
        customer_query
        .filter(Customer.tenant_id == tenant_id, Customer.phone == normalized_phone)
        .order_by(Customer.id.desc())
        .first()
    )

    if not customer:
        return StoreCustomerProfileResponse(found=False, customer=None)

    stats = (
        db.query(CustomerStats)
        .filter(CustomerStats.tenant_id == tenant_id, CustomerStats.phone == normalized_phone)
        .first()
    )

    sorted_addresses = sorted(
        [address for address in (customer.addresses or [])],
        key=lambda entry: (not bool(entry.is_default), -int(entry.id)),
    )

    try:
        points_row = (
            db.query(CustomerPoints)
            .filter(CustomerPoints.tenant_id == tenant_id, CustomerPoints.customer_id == customer.id)
            .first()
        )
    except Exception:
        points_row = None

    return StoreCustomerProfileResponse(
        found=True,
        customer=StoreCustomerProfileRead(
            id=customer.id,
            name=customer.name,
            phone=customer.phone,
            email=customer.email,
            addresses=[
                CustomerProfileAddressRead(
                    id=address.id,
                    zip=address.cep or address.zip,
                    street=address.street,
                    number=address.number,
                    complement=address.complement,
                    neighborhood=address.neighborhood,
                    city=address.city,
                    state=address.state,
                    is_default=bool(address.is_default),
                )
                for address in sorted_addresses
            ],
            points=(
                StoreCustomerPointsRead(
                    available=int(points_row.available_points or 0),
                    lifetime=int(points_row.lifetime_points or 0),
                )
                if points_row
                else None
            ),
            active_benefits=[
                StoreCustomerActiveBenefitRead(
                    id=benefit.id,
                    type=benefit.benefit_type,
                    value=float(benefit.benefit_value or 0),
                    coupon_code=benefit.coupon_code,
                )
                for benefit in ((customer.benefits or []) if benefits_table_exists else [])
                if benefit.tenant_id == tenant_id and bool(benefit.active)
            ],
            tags=[
                tag.tag
                for tag in (customer.tags or [])
                if tag.tenant_id == tenant_id
            ],
            stats=(
                StoreCustomerStatsRead(
                    total_orders=int(stats.total_orders or 0),
                    total_spent=float(stats.total_spent or 0),
                )
                if stats
                else None
            ),
        ),
    )


@router.patch("/customer-profile/{customer_id}", response_model=CustomerProfileResponse)
def update_customer_profile(
    customer_id: int,
    payload: CustomerProfileUpdatePayload,
    request: Request,
    db: Session = Depends(get_db),
):
    tenant_id = _resolve_tenant_id(request)
    customer = _get_customer_or_404(db, tenant_id, customer_id)

    if payload.name is not None:
        customer.name = payload.name.strip() or customer.name
    if payload.phone is not None:
        customer.phone = payload.phone.strip() or customer.phone
    if payload.email is not None:
        customer.email = payload.email.strip() or None

    db.add(customer)
    db.commit()
    db.refresh(customer)

    addresses = (
        db.query(CustomerAddress)
        .filter(CustomerAddress.customer_id == customer.id)
        .order_by(CustomerAddress.id.desc())
        .all()
    )
    return {
        "id": customer.id,
        "name": customer.name,
        "phone": customer.phone,
        "email": customer.email,
        "addresses": [_address_payload(address) | {"id": address.id} for address in addresses],
    }


@router.get("/customer-orders", response_model=list[CustomerOrdersResponseItem])
def list_customer_orders(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    tenant_id = _resolve_tenant_id(request)
    _get_customer_or_404(db, tenant_id, customer_id)

    orders = (
        db.query(Order)
        .filter(Order.tenant_id == tenant_id, Order.customer_id == customer_id)
        .order_by(Order.created_at.desc())
        .limit(50)
        .all()
    )

    order_ids = [order.id for order in orders]
    items_map: dict[int, list[str]] = {}
    if order_ids:
        items = db.query(OrderItem).filter(OrderItem.order_id.in_(order_ids)).all()
        for item in items:
            items_map.setdefault(item.order_id, []).append(f"{item.quantity}x {item.name}")

    return [
        {
            "id": order.id,
            "order_number": order.daily_order_number,
            "date": order.created_at,
            "items": items_map.get(order.id, [order.itens] if order.itens else []),
            "total": int(order.total_cents or order.valor_total or 0),
        }
        for order in orders
    ]


@router.get("/customer-discounts", response_model=CustomerDiscountsResponse)
def get_customer_discounts(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    tenant_id = _resolve_tenant_id(request)
    _get_customer_or_404(db, tenant_id, customer_id)

    total_orders, total_spent = (
        db.query(
            func.count(Order.id),
            func.coalesce(func.sum(func.coalesce(Order.total_cents, Order.valor_total)), 0),
        )
        .filter(Order.tenant_id == tenant_id, Order.customer_id == customer_id)
        .one()
    )
    return {
        "is_vip": _is_vip_customer(db, tenant_id, customer_id),
        "total_orders": int(total_orders or 0),
        "total_spent": int(total_spent or 0),
    }


@router.post("/orders", response_model=PublicOrderCreateResponse)
async def create_store_order(
    payload: PublicOrderPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    tenant_id = int(payload.store_id) if payload.store_id is not None else _resolve_tenant_id(request)
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Loja não encontrada")

    return await _create_order_for_tenant(db=db, tenant=tenant, payload=payload)


@router.get("/cep/{cep}", response_model=CepLookupResponse)
async def get_cep_address(cep: str):
    payload = await lookup_cep(cep)
    if payload is None:
        raise HTTPException(status_code=404, detail="CEP não encontrado")
    return CepLookupResponse(**payload)

@router.post("/validate-coupon", response_model=ValidateCouponResponse)
def validate_coupon(
    payload: ValidateCouponPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    tenant_id = _resolve_tenant_id(request)
    code = payload.code.strip().upper()
    order_total = Decimal(str(payload.order_total or 0))

    if not code:
        return ValidateCouponResponse(valid=False, discount_amount=0.0, new_total=float(order_total), message="Cupom inválido")
    if order_total <= 0:
        return ValidateCouponResponse(valid=False, discount_amount=0.0, new_total=0.0, message="Total do pedido inválido")

    coupon = (
        db.query(Coupon)
        .filter(Coupon.tenant_id == tenant_id, func.upper(Coupon.code) == code)
        .first()
    )
    if not coupon:
        return ValidateCouponResponse(valid=False, discount_amount=0.0, new_total=float(order_total), message="Cupom não encontrado")
    if not coupon.active:
        return ValidateCouponResponse(valid=False, discount_amount=0.0, new_total=float(order_total), message="Cupom inativo")

    now = datetime.now(timezone.utc)
    if coupon.expires_at:
        expires_at = coupon.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now:
            return ValidateCouponResponse(valid=False, discount_amount=0.0, new_total=float(order_total), message="Cupom expirado")

    if coupon.max_uses is not None and int(coupon.uses_count or 0) >= int(coupon.max_uses):
        return ValidateCouponResponse(valid=False, discount_amount=0.0, new_total=float(order_total), message="Cupom esgotado")

    if coupon.min_order_value is not None and order_total < Decimal(str(coupon.min_order_value)):
        return ValidateCouponResponse(valid=False, discount_amount=0.0, new_total=float(order_total), message="Valor mínimo do pedido não atingido")

    if coupon.vip_only:
        if payload.customer_id is None:
            return ValidateCouponResponse(valid=False, discount_amount=0.0, new_total=float(order_total), message="Cupom exclusivo para clientes VIP")
        if not _is_vip_customer(db, tenant_id=tenant_id, customer_id=payload.customer_id):
            return ValidateCouponResponse(valid=False, discount_amount=0.0, new_total=float(order_total), message="Cliente não é VIP")

    discount_amount = Decimal("0")
    coupon_type = (coupon.type or "").strip().lower()
    if coupon_type == "percentage":
        discount_amount = order_total * (Decimal(str(coupon.value)) / Decimal("100"))
    elif coupon_type == "fixed":
        discount_amount = Decimal(str(coupon.value))
    else:
        return ValidateCouponResponse(valid=False, discount_amount=0.0, new_total=float(order_total), message="Tipo de cupom inválido")

    if discount_amount > order_total:
        discount_amount = order_total
    if discount_amount < 0:
        discount_amount = Decimal("0")

    new_total = order_total - discount_amount
    return ValidateCouponResponse(
        valid=True,
        discount_amount=float(discount_amount),
        new_total=float(new_total),
        message="Cupom válido",
    )
