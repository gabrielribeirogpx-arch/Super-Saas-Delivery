from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.customer_stats import CustomerStats
from app.models.order import Order


def is_customer_opted_in(db: Session, tenant_id: int, phone: str) -> bool:
    if not phone:
        return False
    stats = (
        db.query(CustomerStats)
        .filter(CustomerStats.tenant_id == tenant_id, CustomerStats.phone == phone)
        .first()
    )
    if stats is None:
        return True
    return bool(stats.opt_in)


def update_customer_stats_for_order(db: Session, order: Order) -> CustomerStats:
    stats = (
        db.query(CustomerStats)
        .filter(CustomerStats.tenant_id == order.tenant_id, CustomerStats.phone == order.cliente_telefone)
        .first()
    )
    if stats is None:
        stats = CustomerStats(
            tenant_id=order.tenant_id,
            phone=order.cliente_telefone,
            total_orders=0,
            total_spent=0,
            opt_in=True,
        )
        db.add(stats)

    stats.total_orders = int(stats.total_orders or 0) + 1
    stats.total_spent = int(stats.total_spent or 0) + int(order.total_cents or order.valor_total or 0)
    stats.last_order_at = order.created_at
    return stats
