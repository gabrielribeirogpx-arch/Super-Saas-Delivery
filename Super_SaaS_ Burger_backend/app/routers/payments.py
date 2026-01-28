from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.finance import OrderPayment, CashMovement
from app.models.order import Order
from app.services.finance import (
    ALLOWED_PAYMENT_STATUSES,
    create_order_payment,
    create_cash_movement,
    utcnow,
)

router = APIRouter(prefix="/api", tags=["payments"])


class OrderPaymentCreate(BaseModel):
    method: str
    amount_cents: int = Field(..., gt=0)
    fee_cents: int = Field(0, ge=0)
    status: Optional[str] = "paid"


class OrderPaymentUpdateStatus(BaseModel):
    status: str


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


def _ensure_order(db: Session, order_id: int) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return order


@router.post("/orders/{order_id}/payments", response_model=OrderPaymentRead)
def create_payment(
    order_id: int,
    payload: OrderPaymentCreate,
    db: Session = Depends(get_db),
):
    order = _ensure_order(db, order_id)

    try:
        payment = create_order_payment(
            db,
            order=order,
            method=payload.method,
            amount_cents=payload.amount_cents,
            fee_cents=payload.fee_cents,
            status=payload.status or "paid",
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
def list_payments(order_id: int, db: Session = Depends(get_db)):
    order = _ensure_order(db, order_id)
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
):
    order = _ensure_order(db, order_id)
    payment = (
        db.query(OrderPayment)
        .filter(
            OrderPayment.id == payment_id,
            OrderPayment.order_id == order.id,
            OrderPayment.tenant_id == order.tenant_id,
        )
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")

    new_status = (payload.status or "").strip().lower()
    if new_status not in ALLOWED_PAYMENT_STATUSES:
        raise HTTPException(status_code=400, detail="Status inválido")

    if payment.status == new_status:
        return _payment_to_dict(payment)

    existing_categories = {
        movement.category
        for movement in db.query(CashMovement)
        .filter(
            CashMovement.reference_type == "order_payment",
            CashMovement.reference_id == payment.id,
            CashMovement.tenant_id == payment.tenant_id,
        )
        .all()
    }

    try:
        if new_status == "paid":
            payment.paid_at = payment.paid_at or utcnow()
            payment.status = "paid"
            if "sale" not in existing_categories:
                create_cash_movement(
                    db,
                    tenant_id=payment.tenant_id,
                    movement_type="in",
                    category="sale",
                    amount_cents=payment.amount_cents,
                    reference_type="order_payment",
                    reference_id=payment.id,
                )
            if payment.fee_cents > 0 and "fee" not in existing_categories:
                create_cash_movement(
                    db,
                    tenant_id=payment.tenant_id,
                    movement_type="out",
                    category="fee",
                    amount_cents=payment.fee_cents,
                    reference_type="order_payment",
                    reference_id=payment.id,
                )
        elif new_status == "refunded":
            payment.status = "refunded"
            if "refund" not in existing_categories:
                create_cash_movement(
                    db,
                    tenant_id=payment.tenant_id,
                    movement_type="out",
                    category="refund",
                    amount_cents=payment.amount_cents,
                    reference_type="order_payment",
                    reference_id=payment.id,
                )
        elif new_status == "canceled":
            was_paid = payment.status == "paid"
            payment.status = "canceled"
            if was_paid and "adjustment" not in existing_categories:
                create_cash_movement(
                    db,
                    tenant_id=payment.tenant_id,
                    movement_type="out",
                    category="adjustment",
                    amount_cents=payment.amount_cents,
                    reference_type="order_payment",
                    reference_id=payment.id,
                    description="cancelamento de pagamento",
                )
        else:
            payment.status = new_status

        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Erro ao atualizar pagamento") from exc

    db.refresh(payment)
    return _payment_to_dict(payment)
