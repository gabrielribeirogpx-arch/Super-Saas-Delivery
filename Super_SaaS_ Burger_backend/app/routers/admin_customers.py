from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.customer import Customer
from app.models.customer_address import CustomerAddress
from app.models.order import Order

router = APIRouter(prefix="/api/admin/customers", tags=["admin-customers"])


class AdminCustomerListItem(BaseModel):
    id: int
    name: str
    phone: str
    total_orders: int
    total_spent: int
    last_order_date: datetime | None


class AdminCustomerListResponse(BaseModel):
    items: list[AdminCustomerListItem]
    total: int
    page: int


class AdminCustomerOrderRead(BaseModel):
    id: int
    status: str
    total_cents: int
    created_at: datetime


class AdminCustomerDetailResponse(BaseModel):
    id: int
    name: str
    phone: str
    address: str | None
    total_orders: int
    total_spent: int
    orders: list[AdminCustomerOrderRead]


def _resolve_tenant(user: AdminUser, tenant_id: Optional[int]) -> int:
    resolved_tenant_id = tenant_id if tenant_id is not None else int(user.tenant_id)
    if int(user.tenant_id) != int(resolved_tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant não autorizado")
    return resolved_tenant_id


@router.get("", response_model=AdminCustomerListResponse)
def list_admin_customers(
    tenant_id: Optional[int] = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    resolved_tenant_id = _resolve_tenant(user, tenant_id)

    filters = [Customer.tenant_id == resolved_tenant_id]
    clean_search = (search or "").strip()
    if clean_search:
        search_like = f"%{clean_search}%"
        filters.append(or_(Customer.name.ilike(search_like), Customer.phone.ilike(search_like)))

    total = db.query(func.count(Customer.id)).filter(*filters).scalar() or 0

    order_join = and_(Order.customer_id == Customer.id, Order.tenant_id == resolved_tenant_id)
    offset = (page - 1) * limit

    rows = (
        db.query(
            Customer.id,
            Customer.name,
            Customer.phone,
            func.count(Order.id).label("total_orders"),
            func.coalesce(func.sum(func.coalesce(Order.total_cents, Order.valor_total)), 0).label("total_spent"),
            func.max(Order.created_at).label("last_order_date"),
        )
        .outerjoin(Order, order_join)
        .filter(*filters)
        .group_by(Customer.id, Customer.name, Customer.phone)
        .order_by(func.max(Order.created_at).desc().nullslast(), Customer.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    items = []
    for row in rows:
        total_spent = row.total_spent if row.total_spent is not None else 0
        if isinstance(total_spent, Decimal):
            total_spent = int(total_spent)
        items.append(
            {
                "id": row.id,
                "name": row.name,
                "phone": row.phone,
                "total_orders": int(row.total_orders or 0),
                "total_spent": int(total_spent),
                "last_order_date": row.last_order_date,
            }
        )

    return {
        "items": items,
        "total": int(total),
        "page": page,
    }


@router.get("/{customer_id}", response_model=AdminCustomerDetailResponse)
def get_admin_customer(
    customer_id: int,
    tenant_id: Optional[int] = None,
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    resolved_tenant_id = _resolve_tenant(user, tenant_id)

    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.tenant_id == resolved_tenant_id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")

    aggregated = (
        db.query(
            func.count(Order.id).label("total_orders"),
            func.coalesce(func.sum(func.coalesce(Order.total_cents, Order.valor_total)), 0).label("total_spent"),
        )
        .filter(Order.customer_id == customer.id, Order.tenant_id == resolved_tenant_id)
        .first()
    )

    orders = (
        db.query(Order)
        .filter(Order.customer_id == customer.id, Order.tenant_id == resolved_tenant_id)
        .order_by(Order.created_at.desc())
        .limit(100)
        .all()
    )

    address_row = (
        db.query(CustomerAddress)
        .filter(CustomerAddress.customer_id == customer.id)
        .order_by(CustomerAddress.id.desc())
        .first()
    )

    address = None
    if address_row:
        parts = [
            f"{address_row.street}, {address_row.number}",
            address_row.complement,
            address_row.district,
            f"{address_row.city} - {address_row.zip}",
        ]
        address = ", ".join([part for part in parts if part])

    total_spent = aggregated.total_spent if aggregated and aggregated.total_spent is not None else 0
    if isinstance(total_spent, Decimal):
        total_spent = int(total_spent)

    return {
        "id": customer.id,
        "name": customer.name,
        "phone": customer.phone,
        "address": address,
        "total_orders": int(aggregated.total_orders or 0) if aggregated else 0,
        "total_spent": int(total_spent),
        "orders": [
            {
                "id": order.id,
                "status": order.status,
                "total_cents": int(order.total_cents or order.valor_total or 0),
                "created_at": order.created_at,
            }
            for order in orders
        ],
    }
