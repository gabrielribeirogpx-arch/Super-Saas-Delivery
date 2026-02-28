from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.customer import Customer
from app.models.order import Order

router = APIRouter(prefix="/api/admin/customers", tags=["admin-customers"])


class AdminCustomerRead(BaseModel):
    id: int
    name: str
    phone: str
    total_orders: int
    last_order_date: datetime | None


@router.get("", response_model=list[AdminCustomerRead])
def list_admin_customers(
    tenant_id: Optional[int] = None,
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    resolved_tenant_id = tenant_id if tenant_id is not None else int(user.tenant_id)

    if int(user.tenant_id) != int(resolved_tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant não autorizado")

    rows = (
        db.query(
            Customer.id,
            Customer.name,
            Customer.phone,
            func.count(Order.id).label("total_orders"),
            func.max(Order.created_at).label("last_order_date"),
        )
        .outerjoin(Order, Order.customer_id == Customer.id)
        .filter(Customer.tenant_id == resolved_tenant_id)
        .group_by(Customer.id, Customer.name, Customer.phone)
        .order_by(Customer.id.desc())
        .all()
    )

    return [
        {
            "id": row.id,
            "name": row.name,
            "phone": row.phone,
            "total_orders": int(row.total_orders or 0),
            "last_order_date": row.last_order_date,
        }
        for row in rows
    ]
