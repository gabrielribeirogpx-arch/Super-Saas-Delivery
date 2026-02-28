from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_
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
    average_ticket: float
    first_order_date: datetime | None
    last_order_date: datetime | None
    days_since_last_order: int | None
    recurrence_segment: str
    is_vip: bool


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
    vip_only: bool = Query(default=False),
    recurrence: str | None = Query(default=None, pattern="^(frequent|regular|occasional|inactive)$"),
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    resolved_tenant_id = _resolve_tenant(user, tenant_id)

    filters = [Customer.tenant_id == resolved_tenant_id]
    clean_search = (search or "").strip()
    if clean_search:
        search_like = f"%{clean_search}%"
        filters.append(or_(Customer.name.ilike(search_like), Customer.phone.ilike(search_like)))

    aggregates = (
        db.query(
            Order.customer_id.label("customer_id"),
            func.count(Order.id).label("total_orders"),
            func.coalesce(func.sum(func.coalesce(Order.total_cents, Order.valor_total)), 0).label("total_spent"),
            func.min(Order.created_at).label("first_order_date"),
            func.max(Order.created_at).label("last_order_date"),
        )
        .filter(Order.tenant_id == resolved_tenant_id)
        .group_by(Order.customer_id)
        .subquery()
    )

    query = db.query(
        Customer.id,
        Customer.name,
        Customer.phone,
        func.coalesce(aggregates.c.total_orders, 0).label("total_orders"),
        func.coalesce(aggregates.c.total_spent, 0).label("total_spent"),
        aggregates.c.first_order_date.label("first_order_date"),
        aggregates.c.last_order_date.label("last_order_date"),
    ).outerjoin(aggregates, aggregates.c.customer_id == Customer.id)

    now = datetime.utcnow()
    days_15 = now - timedelta(days=15)
    days_45 = now - timedelta(days=45)
    days_90 = now - timedelta(days=90)

    if vip_only:
        query = query.filter(
            or_(
                func.coalesce(aggregates.c.total_spent, 0) >= 500,
                func.coalesce(aggregates.c.total_orders, 0) >= 10,
            )
        )

    if recurrence == "frequent":
        query = query.filter(aggregates.c.last_order_date.isnot(None), aggregates.c.last_order_date > days_15)
    elif recurrence == "regular":
        query = query.filter(aggregates.c.last_order_date <= days_15, aggregates.c.last_order_date > days_45)
    elif recurrence == "occasional":
        query = query.filter(aggregates.c.last_order_date <= days_45, aggregates.c.last_order_date > days_90)
    elif recurrence == "inactive":
        query = query.filter(
            or_(aggregates.c.last_order_date.is_(None), aggregates.c.last_order_date <= days_90)
        )

    query = query.filter(*filters)

    total = query.with_entities(func.count(Customer.id)).scalar() or 0
    offset = (page - 1) * limit

    rows = (
        query.order_by(aggregates.c.last_order_date.desc().nullslast(), Customer.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    items = []
    for row in rows:
        total_spent = row.total_spent if row.total_spent is not None else 0
        if isinstance(total_spent, Decimal):
            total_spent = int(total_spent)
        total_orders = int(row.total_orders or 0)
        average_ticket = float(total_spent / total_orders) if total_orders > 0 else 0.0
        last_order_date = row.last_order_date
        days_since_last_order = None
        if last_order_date is not None:
            days_since_last_order = max((now - last_order_date.replace(tzinfo=None)).days, 0)

        if days_since_last_order is None or days_since_last_order >= 90:
            recurrence_segment = "inactive"
        elif days_since_last_order < 15:
            recurrence_segment = "frequent"
        elif days_since_last_order < 45:
            recurrence_segment = "regular"
        else:
            recurrence_segment = "occasional"

        items.append(
            {
                "id": row.id,
                "name": row.name,
                "phone": row.phone,
                "total_orders": total_orders,
                "total_spent": int(total_spent),
                "average_ticket": average_ticket,
                "first_order_date": row.first_order_date,
                "last_order_date": last_order_date,
                "days_since_last_order": days_since_last_order,
                "recurrence_segment": recurrence_segment,
                "is_vip": bool(total_spent >= 500 or total_orders >= 10),
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
