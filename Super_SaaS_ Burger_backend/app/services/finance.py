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
