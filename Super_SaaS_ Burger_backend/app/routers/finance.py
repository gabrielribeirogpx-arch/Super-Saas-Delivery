from datetime import date, datetime, time
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_request_tenant_id, require_role
from app.models.admin_user import AdminUser
from app.models.finance import CashMovement, OrderPayment
from app.models.order import Order
from app.models.admin_audit_log import AdminAuditLog
from app.models.native_payment import NativePaymentIntent
from app.services.finance import MANUAL_PAYMENT_METHODS, CANCELED_ORDER_STATUSES, normalize_payment_method

router = APIRouter(prefix="/api/finance", tags=["finance"])


class CashMovementRead(BaseModel):
    id: int
    tenant_id: int
    type: str
    category: str
    description: str | None
    amount_cents: int
    reference_type: str | None
    reference_id: int | None
    occurred_at: datetime
    created_at: datetime


class CashSummaryRead(BaseModel):
    opening_balance_cents: int
    total_in_cents: int
    total_out_cents: int
    net_cents: int
    by_category: Dict[str, int]


def _parse_date(value: str) -> date:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.date()
    except ValueError:
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Data inválida") from exc


def _date_range(from_str: str, to_str: str) -> tuple[datetime, datetime]:
    start_date = _parse_date(from_str)
    end_date = _parse_date(to_str)
    start = datetime.combine(start_date, time.min)
    end = datetime.combine(end_date, time.max)
    return start, end


def _movement_to_dict(movement: CashMovement) -> dict:
    return {
        "id": movement.id,
        "tenant_id": movement.tenant_id,
        "type": movement.type,
        "category": movement.category,
        "description": movement.description,
        "amount_cents": movement.amount_cents,
        "reference_type": movement.reference_type,
        "reference_id": movement.reference_id,
        "occurred_at": movement.occurred_at,
        "created_at": movement.created_at,
    }


@router.get("/cash/summary", response_model=CashSummaryRead)
def cash_summary(
    tenant_id: int = Depends(get_request_tenant_id),
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "cashier"])),
):
    start, end = _date_range(from_date, to_date)
    movements = (
        db.query(CashMovement)
        .filter(
            CashMovement.tenant_id == tenant_id,
            CashMovement.occurred_at >= start,
            CashMovement.occurred_at <= end,
        )
        .all()
    )

    total_in_cents = 0
    total_out_cents = 0
    by_category: Dict[str, int] = {}

    for movement in movements:
        if movement.type == "in":
            total_in_cents += movement.amount_cents
            by_category[movement.category] = by_category.get(movement.category, 0) + movement.amount_cents
        else:
            total_out_cents += movement.amount_cents
            by_category[movement.category] = by_category.get(movement.category, 0) - movement.amount_cents

    net_cents = total_in_cents - total_out_cents

    return {
        "opening_balance_cents": 0,
        "total_in_cents": total_in_cents,
        "total_out_cents": total_out_cents,
        "net_cents": net_cents,
        "by_category": by_category,
    }


@router.get("/cash/movements", response_model=List[CashMovementRead])
def list_cash_movements(
    tenant_id: int = Depends(get_request_tenant_id),
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "cashier"])),
):
    start, end = _date_range(from_date, to_date)
    movements = (
        db.query(CashMovement)
        .filter(
            CashMovement.tenant_id == tenant_id,
            CashMovement.occurred_at >= start,
            CashMovement.occurred_at <= end,
        )
        .order_by(CashMovement.occurred_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_movement_to_dict(movement) for movement in movements]


class ManualPaymentRead(BaseModel):
    id: int
    order_id: int
    order_number: int
    method: str
    amount_cents: int
    status: str
    order_status: str
    created_at: datetime
    paid_at: datetime | None
    confirmed_by: str | None
    can_confirm: bool


class ManualPaymentPage(BaseModel):
    items: List[ManualPaymentRead]
    total: int
    pending_cents: int
    paid_cents: int


@router.get("/manual-payments", response_model=ManualPaymentPage)
def list_manual_payments(
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    payment_status: str = Query("pending", alias="status"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_role(["admin", "cashier"])),
):
    start, end = _date_range(from_date, to_date)
    if start > end:
        raise HTTPException(status_code=400, detail="Período inválido")
    if payment_status not in {"all", "pending", "paid", "canceled", "refunded"}:
        raise HTTPException(status_code=400, detail="Status inválido")
    # This view is scoped by the authenticated actor, never by a caller's tenant ID.
    query = db.query(OrderPayment, Order).join(Order, (Order.id == OrderPayment.order_id) & (Order.tenant_id == OrderPayment.tenant_id)).filter(
        OrderPayment.tenant_id == user.tenant_id,
        OrderPayment.created_at >= start, OrderPayment.created_at <= end,
        func.lower(OrderPayment.method).in_(["cash", "money", "pix", "card", "dinheiro", "cartao", "cartão", "manual_pix", "external_card"]),
        ~db.query(NativePaymentIntent.id).filter(NativePaymentIntent.order_id == Order.id, NativePaymentIntent.tenant_id == Order.tenant_id).exists(),
        ~func.lower(func.coalesce(Order.payment_method, "")).like("native_%"),
        ~func.lower(func.coalesce(Order.forma_pagamento, "")).like("native_%"),
    )
    totals = {status: int(amount) for status, amount in query.with_entities(OrderPayment.status, func.sum(OrderPayment.amount_cents)).group_by(OrderPayment.status).all()}
    if payment_status != "all":
        query = query.filter(OrderPayment.status == payment_status)
    count = query.count()
    rows = query.order_by(OrderPayment.created_at.desc(), OrderPayment.id.desc()).offset(offset).limit(limit).all()
    ids = [payment.id for payment, _ in rows]
    confirmations = {}
    if ids:
        audits = db.query(AdminAuditLog, AdminUser.name).outerjoin(AdminUser, (AdminUser.id == AdminAuditLog.user_id) & (AdminUser.tenant_id == AdminAuditLog.tenant_id)).filter(
            AdminAuditLog.tenant_id == user.tenant_id, AdminAuditLog.entity_type == "order_payment",
            AdminAuditLog.entity_id.in_(ids), AdminAuditLog.action == "confirm_manual_payment",
        ).order_by(AdminAuditLog.id.asc()).all()
        confirmations = {audit.entity_id: name or f"Usuário #{audit.user_id}" for audit, name in audits}
    return {
        "items": [{
            "id": payment.id, "order_id": order.id,
            "order_number": order.daily_order_number or order.id,
            "method": normalize_payment_method(payment.method), "amount_cents": payment.amount_cents,
            "status": payment.status, "order_status": order.status,
            "created_at": payment.created_at, "paid_at": payment.paid_at,
            "confirmed_by": confirmations.get(payment.id),
            "can_confirm": payment.status == "pending" and (order.status or "").strip().upper() not in CANCELED_ORDER_STATUSES,
        } for payment, order in rows],
        "total": count, "pending_cents": totals.get("pending", 0), "paid_cents": totals.get("paid", 0),
    }
