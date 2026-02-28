from __future__ import annotations

from typing import Any
from decimal import Decimal
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.coupon import Coupon
from app.models.customer import Customer
from app.models.customer_address import CustomerAddress
from app.models.order import Order
from app.services.tenant_resolver import TenantResolver

router = APIRouter(prefix="/api/store", tags=["store"])


class StoreCustomerLookupResponse(BaseModel):
    exists: bool
    name: str | None
    address: dict[str, Any] | None


class ValidateCouponPayload(BaseModel):
    code: str
    order_total: float
    customer_id: int | None = None


class ValidateCouponResponse(BaseModel):
    valid: bool
    discount_amount: float
    new_total: float
    message: str


def _resolve_tenant_id(request: Request) -> int:
    tenant = getattr(request.state, "tenant", None)
    if tenant is not None and getattr(tenant, "id", None) is not None:
        return int(tenant.id)

    tenant_id = TenantResolver.resolve_tenant_id_from_request(request)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Tenant não identificado")
    return int(tenant_id)


def _address_payload(address: CustomerAddress | None) -> dict[str, Any] | None:
    if not address:
        return None

    return {
        "street": address.street,
        "number": address.number,
        "district": address.district,
        "city": address.city,
        "zip": address.zip,
        "complement": address.complement,
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


@router.get("/customer-by-phone", response_model=StoreCustomerLookupResponse)
def get_store_customer_by_phone(
    request: Request,
    phone: str = Query(..., min_length=3),
    db: Session = Depends(get_db),
):
    tenant_id = _resolve_tenant_id(request)
    normalized_phone = phone.strip()
    if not normalized_phone:
        return StoreCustomerLookupResponse(exists=False, name=None, address=None)

    customer = (
        db.query(Customer)
        .filter(Customer.tenant_id == tenant_id, Customer.phone == normalized_phone)
        .order_by(Customer.id.desc())
        .first()
    )

    if customer:
        latest_address = (
            db.query(CustomerAddress)
            .filter(CustomerAddress.customer_id == customer.id)
            .order_by(CustomerAddress.id.desc())
            .first()
        )
        return StoreCustomerLookupResponse(
            exists=True,
            name=customer.name,
            address=_address_payload(latest_address),
        )

    latest_order = (
        db.query(Order)
        .filter(
            Order.tenant_id == tenant_id,
            (Order.customer_phone == normalized_phone) | (Order.cliente_telefone == normalized_phone),
        )
        .order_by(Order.id.desc())
        .first()
    )

    if not latest_order:
        return StoreCustomerLookupResponse(exists=False, name=None, address=None)

    fallback_name = (latest_order.customer_name or latest_order.cliente_nome or "").strip() or None
    fallback_address = latest_order.delivery_address_json if isinstance(latest_order.delivery_address_json, dict) else None

    return StoreCustomerLookupResponse(
        exists=bool(fallback_name or fallback_address),
        name=fallback_name,
        address=fallback_address,
    )


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
