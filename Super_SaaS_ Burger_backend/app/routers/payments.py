from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.finance import OrderPayment
from app.models.order import Order
from app.services.admin_audit import log_admin_action
from app.services.finance import (
    ALLOWED_PAYMENT_STATUSES,
    create_order_payment,
    ensure_manual_order,
    ensure_receivable_order,
    validate_manual_allocation,
    transition_manual_payment,
)

router = APIRouter(prefix="/api", tags=["payments"])


class OrderPaymentCreate(BaseModel):
    method: str
    amount_cents: int = Field(..., gt=0)
    fee_cents: int = Field(0, ge=0)
    status: Optional[str] = "paid"


class OrderPaymentUpdateStatus(BaseModel):
    status: str
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if len(cleaned) < 5:
            raise ValueError("Informe um motivo com pelo menos 5 caracteres")
        return cleaned


class OrderPaymentRead(BaseModel):
    id: int
    tenant_id: int
    order_id: int
    method: str
    amount_cents: int
    fee_cents: int
    status: str
    paid_at: Optional[datetime]
    created_at: datetime


def _payment_to_dict(payment: OrderPayment) -> dict:
    return {
        "id": payment.id,
        "tenant_id": payment.tenant_id,
        "order_id": payment.order_id,
        "method": payment.method,
        "amount_cents": payment.amount_cents,
        "fee_cents": payment.fee_cents,
        "status": payment.status,
        "paid_at": payment.paid_at,
        "created_at": payment.created_at,
    }


def _ensure_order(db: Session, order_id: int, user: AdminUser | None = None, *, lock: bool = False) -> Order:
    query = db.query(Order).filter(Order.id == order_id)
    if lock:
        query = query.populate_existing().with_for_update()
    order = query.first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    if user and int(order.tenant_id) != int(user.tenant_id):
        raise HTTPException(status_code=403, detail="Sem permissão para este pedido")
    return order


@router.post("/orders/{order_id}/payments", response_model=OrderPaymentRead)
def create_payment(
    order_id: int,
    payload: OrderPaymentCreate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_role(["admin", "cashier"])),
):
    order = _ensure_order(db, order_id, user, lock=True)

    try:
        ensure_manual_order(db, order, payload.method)
        ensure_receivable_order(order)
        if payload.status not in {None, "pending", "paid"}:
            raise ValueError("Novo pagamento deve estar pendente ou recebido")
        if payload.fee_cents > payload.amount_cents:
            raise ValueError("Taxa não pode exceder o valor recebido")
        validate_manual_allocation(db, order, payload.amount_cents)
        payment = create_order_payment(
            db,
            order=order,
            method=payload.method,
            amount_cents=payload.amount_cents,
            fee_cents=payload.fee_cents,
            status=payload.status or "paid",
        )
        log_admin_action(
            db,
            tenant_id=order.tenant_id,
            user_id=user.id,
            action="register_payment",
            entity_type="order_payment",
            entity_id=payment.id,
            meta={"order_id": order.id, "method": payment.method, "status": payment.status, "amount_cents": payment.amount_cents},
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro ao registrar pagamento") from exc

    db.refresh(payment)
    return _payment_to_dict(payment)


@router.get("/orders/{order_id}/payments", response_model=List[OrderPaymentRead])
def list_payments(
    order_id: int,
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "cashier"])),
):
    order = _ensure_order(db, order_id, _user)
    payments = (
        db.query(OrderPayment)
        .filter(OrderPayment.order_id == order.id, OrderPayment.tenant_id == order.tenant_id)
        .order_by(OrderPayment.created_at.desc())
        .all()
    )
    return [_payment_to_dict(payment) for payment in payments]


@router.post("/orders/{order_id}/payments/{payment_id}/status", response_model=OrderPaymentRead)
def update_payment_status(
    order_id: int,
    payment_id: int,
    payload: OrderPaymentUpdateStatus,
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "cashier"])),
):
    order = _ensure_order(db, order_id, _user, lock=True)
    payment = (
        db.query(OrderPayment)
        .filter_by(id=payment_id, order_id=order.id, tenant_id=order.tenant_id)
        .populate_existing()
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")
    new_status = (payload.status or "").strip().lower()
    if new_status not in ALLOWED_PAYMENT_STATUSES:
        raise HTTPException(status_code=400, detail="Status inválido")
    try:
        transition_manual_payment(db, order, payment, new_status, user_id=_user.id, reason=payload.reason)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro ao atualizar pagamento") from exc
    db.refresh(payment)
    return _payment_to_dict(payment)
