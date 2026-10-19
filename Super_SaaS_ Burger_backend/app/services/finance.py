import unicodedata
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.finance import OrderPayment, CashMovement
from app.models.order import Order
from app.services.inventory import apply_stock_for_order


ALLOWED_PAYMENT_STATUSES = {"pending", "paid", "refunded", "canceled"}
PAYMENT_METHOD_ALIASES = {
    "cartao": "card",
    "cartão": "card",
    "card": "card",
    "credito": "card",
    "crédito": "card",
    "debito": "card",
    "débito": "card",
    "pix": "pix",
    "dinheiro": "cash",
    "cash": "cash",
    "money": "cash",
    "manual_pix": "pix",
    "external_card": "card",
}


def utcnow() -> datetime:
    return datetime.utcnow()


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join([char for char in normalized if not unicodedata.combining(char)])


def normalize_payment_method(method: str) -> str:
    if not method:
        return ""
    lowered = _strip_accents(str(method).strip().lower())
    return PAYMENT_METHOD_ALIASES.get(lowered, lowered)


def create_cash_movement(
    db: Session,
    tenant_id: int,
    movement_type: str,
    category: str,
    amount_cents: int,
    reference_type: str | None = None,
    reference_id: int | None = None,
    description: str | None = None,
    occurred_at: datetime | None = None,
) -> CashMovement:
    movement = CashMovement(
        tenant_id=tenant_id,
        type=movement_type,
        category=category,
        amount_cents=amount_cents,
        reference_type=reference_type,
        reference_id=reference_id,
        description=description,
        occurred_at=occurred_at or utcnow(),
    )
    db.add(movement)
    return movement


def _ensure_paid_movements(
    db: Session,
    payment: OrderPayment,
) -> None:
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


def create_order_payment(
    db: Session,
    order: Order,
    method: str,
    amount_cents: int,
    fee_cents: int = 0,
    status: str = "paid",
) -> OrderPayment:
    normalized_status = (status or "paid").strip().lower()
    if normalized_status not in ALLOWED_PAYMENT_STATUSES:
        raise ValueError("Status inválido para pagamento")

    payment = OrderPayment(
        tenant_id=order.tenant_id,
        order_id=order.id,
        method=normalize_payment_method(method),
        amount_cents=amount_cents,
        fee_cents=fee_cents or 0,
        status=normalized_status,
        paid_at=utcnow() if normalized_status == "paid" else None,
    )
    db.add(payment)
    db.flush()

    if normalized_status == "paid":
        _ensure_paid_movements(db, payment)
        apply_stock_for_order(db, order)

    return payment


def maybe_create_payment_for_order(
    db: Session,
    order: Order,
    payment_method: str | None,
) -> OrderPayment | None:
    normalized_method = normalize_payment_method(payment_method or "")
    if not normalized_method:
        return None

    amount_cents = int(order.total_cents or order.valor_total or 0)
    if amount_cents <= 0:
        return None

    return create_order_payment(
        db,
        order=order,
        method=normalized_method,
        amount_cents=amount_cents,
        fee_cents=0,
        status="paid",
    )


MANUAL_PAYMENT_METHODS = {"cash", "pix", "card"}
CANCELED_ORDER_STATUSES = {"CANCELED", "CANCELLED", "CANCELADO", "CANCELADA"}


def ensure_manual_order(db: Session, order: Order, method: str) -> None:
    """Caller holds the order lock until commit/rollback; native writers use it too."""
    from app.models.native_payment import NativePaymentIntent

    if normalize_payment_method(method) not in MANUAL_PAYMENT_METHODS:
        raise ValueError("Ação disponível apenas para pagamentos recebidos diretamente pela loja")
    if normalize_payment_method(order.payment_method or order.forma_pagamento or "").startswith("native_"):
        raise ValueError("Pagamentos online não podem ser confirmados manualmente")
    if db.query(NativePaymentIntent.id).filter_by(tenant_id=order.tenant_id, order_id=order.id).first():
        raise ValueError("Pagamentos online não podem ser confirmados manualmente")


def ensure_receivable_order(order: Order) -> None:
    if (order.status or "").strip().upper() in CANCELED_ORDER_STATUSES:
        raise ValueError("Pedido cancelado: recebimento manual bloqueado")


def validate_manual_allocation(db: Session, order: Order, amount_cents: int, *, exclude_id: int | None = None) -> None:
    """Do not allocate a second payment on top of an existing pending/paid amount."""
    from sqlalchemy import func
    query = db.query(func.coalesce(func.sum(OrderPayment.amount_cents), 0)).filter(
        OrderPayment.tenant_id == order.tenant_id,
        OrderPayment.order_id == order.id,
        OrderPayment.status.in_(["pending", "paid"]),
    )
    if exclude_id is not None:
        query = query.filter(OrderPayment.id != exclude_id)
    allocated = int(query.scalar())
    total = int(order.total_cents or order.valor_total or 0)
    if amount_cents <= 0 or allocated + amount_cents > total:
        raise ValueError("Valor excede o saldo do pedido; confira os pagamentos existentes")


def transition_manual_payment(db: Session, order: Order, payment: OrderPayment, new_status: str, *, user_id: int) -> bool:
    """Atomic financial transition. Caller locks order first and owns transaction."""
    from app.services.admin_audit import log_admin_action

    ensure_manual_order(db, order, payment.method)
    old_status = payment.status
    if old_status == new_status:
        return False
    transitions = {"pending": {"paid", "canceled"}, "paid": {"refunded", "canceled"}}
    if new_status not in transitions.get(old_status, set()):
        raise ValueError("Transição de pagamento não permitida")
    if new_status == "paid":
        ensure_receivable_order(order)
        validate_manual_allocation(db, order, payment.amount_cents, exclude_id=payment.id)
    # Compare-and-set is also effective on SQLite and protects stale clients.
    values = {"status": new_status}
    if new_status == "paid":
        values["paid_at"] = utcnow()
    changed = db.query(OrderPayment).filter_by(
        id=payment.id, tenant_id=order.tenant_id, order_id=order.id, status=old_status,
    ).update(values, synchronize_session=False)
    if changed != 1:
        raise ValueError("Pagamento alterado por outra pessoa; atualize a lista")
    db.refresh(payment)
    if new_status == "paid":
        _ensure_paid_movements(db, payment)
        apply_stock_for_order(db, order)
    elif old_status == "paid":
        create_cash_movement(
            db, tenant_id=order.tenant_id, movement_type="out",
            category="refund" if new_status == "refunded" else "adjustment",
            amount_cents=payment.amount_cents, reference_type="order_payment", reference_id=payment.id,
            description="Estorno registrado pela loja" if new_status == "refunded" else "Cancelamento registrado pela loja",
        )
    log_admin_action(
        db, tenant_id=order.tenant_id, user_id=user_id,
        action="confirm_manual_payment" if new_status == "paid" else "update_manual_payment_status",
        entity_type="order_payment", entity_id=payment.id,
        meta={"order_id": order.id, "from_status": old_status, "to_status": new_status,
              "method": payment.method, "amount_cents": payment.amount_cents},
    )
    return True
