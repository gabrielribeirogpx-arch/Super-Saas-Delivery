from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.customer import Customer
from app.models.customer_address import CustomerAddress
from app.models.order import Order
from app.services.tenant_resolver import TenantResolver

router = APIRouter(prefix="/api/store", tags=["store"])


class StoreCustomerLookupResponse(BaseModel):
    exists: bool
    name: str | None
    address: dict[str, Any] | None


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
