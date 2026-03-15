from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.customer_points import CustomerPoints
from app.models.marketing import CustomerPointTransaction
from app.models.order import Order
from app.models.tenant import Tenant

DELIVERED_STATUSES = {"DELIVERED", "ENTREGUE"}


def resolve_reais_por_ponto(tenant: Tenant) -> float:
    configured_reais_por_ponto = getattr(tenant, "reais_por_ponto", None)
    if configured_reais_por_ponto is not None:
        try:
            reais_por_ponto = float(configured_reais_por_ponto)
            if reais_por_ponto > 0:
                return reais_por_ponto
        except (TypeError, ValueError):
            pass

    points_per_real = float(getattr(tenant, "points_per_real", 1) or 1)
    if points_per_real <= 0:
        return 1
    return 1 / points_per_real


def calculate_order_points(total_cents: int | float | None, reais_por_ponto: float) -> int:
    if reais_por_ponto <= 0:
        return 0

    total_reais = float(total_cents or 0) / 100
    return int(total_reais / reais_por_ponto)


def award_points_for_completed_order(db: Session, order: Order) -> int:
    customer_id = getattr(order, "customer_id", None)
    if not customer_id:
        return 0

    tenant = db.query(Tenant).filter(Tenant.id == order.tenant_id).first()
    if not tenant or not bool(getattr(tenant, "points_enabled", False)):
        return 0

    existing = (
        db.query(CustomerPointTransaction)
        .filter(
            CustomerPointTransaction.tenant_id == order.tenant_id,
            CustomerPointTransaction.order_id == order.id,
        )
        .first()
    )
    if existing:
        return 0

    reais_por_ponto = resolve_reais_por_ponto(tenant)
    points = calculate_order_points(order.total_cents or order.valor_total, reais_por_ponto)
    if points <= 0:
        return 0

    points_row = (
        db.query(CustomerPoints)
        .filter(CustomerPoints.tenant_id == order.tenant_id, CustomerPoints.customer_id == customer_id)
        .first()
    )
    if points_row is None:
        points_row = CustomerPoints(
            tenant_id=order.tenant_id,
            customer_id=customer_id,
            available_points=0,
            lifetime_points=0,
        )
        db.add(points_row)
        db.flush()

    expires_at = None
    expiration_days = getattr(tenant, "points_expiration_days", None)
    if expiration_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=int(expiration_days))

    points_row.available_points = int(points_row.available_points or 0) + points
    points_row.lifetime_points = int(points_row.lifetime_points or 0) + points
    db.add(
        CustomerPointTransaction(
            tenant_id=order.tenant_id,
            customer_id=customer_id,
            order_id=order.id,
            points_delta=points,
            reason="order_completed",
            expires_at=expires_at,
        )
    )
    return points
