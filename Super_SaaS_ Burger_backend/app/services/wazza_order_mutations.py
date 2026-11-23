"""Prepare, confirm and review customer changes to existing orders."""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import hmac
import json
import time

from fastapi import HTTPException
from pydantic import Field
from sqlalchemy import update

from app.core import config
from app.models.coupon import CouponRedemption
from app.models.finance import CashMovement, OrderPayment
from app.models.inventory import InventoryMovement
from app.models.marketing import CustomerPointTransaction
from app.models.native_payment import NativePaymentIntent
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.tenant import Tenant
from app.models.wazza_mcp import WazzaOrderMutation
from app.services.admin_audit import log_admin_action
from app.services.checkout_policy import enforce_checkout_payment
from app.services.finance import MANUAL_PAYMENT_METHODS, transition_manual_payment
from app.services.order_outbox import enqueue_order_status_changed, enqueue_wazza_order_mutation
from app.services.order_statuses import canonical_status
from app.services.orders import _build_items_text, create_order_items
from app.services.wazza_mcp_customer_tools import _owned_orders_query
from app.services.wazza_mcp_errors import McpToolError
from app.services.wazza_mcp_order_drafts import StrictArguments, _money_cents, _price_line
from app.services.wazza_order_policy import CustomerOrderAction, MutationDisposition, decide_customer_mutation

CANCELED = {"CANCELADO", "CANCELED", "CANCELLED"}
ALLOWED = {"RECEBIDO", "EM_PREPARO"}


class RequestedItem(StrictArguments):
    item_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=50)
    modifier_option_ids: list[int] = Field(default_factory=list, max_length=30)


class OrderChangeArguments(StrictArguments):
    order_id: int = Field(gt=0)
    idempotency_key: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    confirmation_token: str | None = Field(default=None, pattern=r"^[0-9]{1,12}\.[a-f0-9]{64}$")


class EditArguments(OrderChangeArguments):
    items: list[RequestedItem] = Field(min_length=1, max_length=50)


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _digest(value):
    return hashlib.sha256(_encode(value)).hexdigest()


def _lock_order(db, query, tenant_id, order_id):
    if db.get_bind().dialect.name == "sqlite":
        db.execute(update(Order).where(Order.id == order_id, Order.tenant_id == tenant_id).values(id=Order.id))
    return query.filter(Order.id == order_id).populate_existing().with_for_update().first()


def _payments(db, order):
    return db.query(OrderPayment).filter_by(tenant_id=order.tenant_id, order_id=order.id).order_by(OrderPayment.id).all()


def _native(db, order):
    return db.query(NativePaymentIntent.id).filter_by(tenant_id=order.tenant_id, order_id=order.id).first() is not None


def _effects(db, order):
    linked = {"tenant_id": order.tenant_id, "order_id": order.id}
    return bool(
        order.coupon_id or order.discount_amount
        or db.query(CouponRedemption.id).filter_by(order_id=order.id).first()
        or db.query(CustomerPointTransaction.id).filter_by(**linked).first()
        or db.query(InventoryMovement.id).filter_by(**linked).first()
    )


def _manual_pending(db, order, payments):
    if len(payments) != 1 or _native(db, order):
        return None
    payment = payments[0]
    if (
        payment.status != "pending" or payment.paid_at or payment.fee_cents
        or payment.method not in MANUAL_PAYMENT_METHODS
        or payment.amount_cents != order.total_cents
        or db.query(CashMovement.id).filter_by(
            tenant_id=order.tenant_id, reference_type="order_payment", reference_id=payment.id,
        ).first()
    ):
        return None
    return payment


def _can_apply(db, order, payments):
    return (
        _manual_pending(db, order, payments) is not None
        and not _effects(db, order)
        and not (order.assigned_delivery_user_id or order.ready_at or order.start_delivery_at)
    )


def _reason(db, order, payments):
    if order.channel != "wazza_mcp":
        return "other_channel"
    if _manual_pending(db, order, payments) is None:
        return "payment_review"
    if _effects(db, order):
        return "benefits_or_stock"
    if order.assigned_delivery_user_id or order.ready_at or order.start_delivery_at:
        return "operational_review"
    if canonical_status(order.status) == "EM_PREPARO":
        return "in_preparation"
    return "customer_confirmed"


def _current_lines(db, order):
    rows = db.query(OrderItem).filter_by(tenant_id=order.tenant_id, order_id=order.id).order_by(OrderItem.id)
    return [{
        "menu_item_id": row.menu_item_id, "name": row.name, "quantity": row.quantity,
        "unit_price_cents": row.unit_price_cents, "subtotal_cents": row.subtotal_cents,
        "modifiers": [{
            key: modifier.get(key) for key in ("group_id", "option_id", "price_cents", "option_name")
        } for modifier in (row.modifiers or []) if isinstance(modifier, dict)],
    } for row in rows]


def _compact(lines):
    return [{
        **{key: line[key] for key in ("menu_item_id", "name", "quantity", "unit_price_cents", "subtotal_cents")},
        "modifiers": [{key: value[key] for key in ("group_id", "option_id", "price_cents", "option_name")} for value in line["modifiers"]],
    } for line in lines]


def _price(db, order, items):
    lines = []
    for index, item in enumerate(items):
        quoted = _price_line(
            db, order.tenant_id, item["item_id"], item["quantity"],
            item["modifier_option_ids"], None, line_id=str(index), lock=True,
        )
        lines.append({
            "menu_item_id": quoted["item_id"], "name": quoted["name"],
            "quantity": quoted["quantity"], "unit_price_cents": quoted["base_price_cents"],
            "subtotal_cents": quoted["subtotal_cents"],
            "modifiers": [{**modifier, "name": modifier["option_name"]} for modifier in quoted["modifiers"]],
        })
    fee_query = db.query(Tenant.delivery_fee).filter(Tenant.id == order.tenant_id)
    fee = _money_cents(fee_query.with_for_update(read=True, key_share=True).scalar()) if order.order_type == "delivery" else 0
    return lines, fee


def _snapshot(db, order, payments):
    return {
        "status": canonical_status(order.status), "channel": order.channel,
        "total_cents": order.total_cents, "fee_cents": _money_cents(order.delivery_fee),
        "lines": _current_lines(db, order),
        "payments": [[p.id, p.status, p.method, p.amount_cents] for p in payments],
        "fulfillment_hash": _digest([order.order_type, order.delivery_address_json]),
        "revision": db.query(WazzaOrderMutation.id).filter_by(
            tenant_id=order.tenant_id, order_id=order.id, state="applied",
        ).order_by(WazzaOrderMutation.id.desc()).limit(1).scalar(),
    }


def _proposal(db, order, action, items):
    payments = _payments(db, order)
    old = _snapshot(db, order, payments)
    reason = _reason(db, order, payments)
    lines, fee = _price(db, order, items) if action == "edit" else ([], 0)
    return {
        "before": old, "items": items, "lines": lines, "fee_cents": fee,
        "total_cents": sum(line["subtotal_cents"] for line in lines) + fee,
        "reason": reason,
    }


def _apply(db, order, record, user_id=None):
    payment = _manual_pending(db, order, _payments(db, order))
    if payment is None or not _can_apply(db, order, [payment]):
        raise McpToolError("requires_manual_resolution", "Pagamento ou efeitos exigem resolução manual.")
    if record.action == "cancel":
        transition_manual_payment(
            db, order, payment, "canceled", user_id=user_id, reason="Cancelamento solicitado via Wazza",
        )
        previous = order.status
        order.status = "CANCELADO"
        enqueue_order_status_changed(db, order, previous)
    else:
        enforce_checkout_payment(db, order.tenant_id, order.payment_method)
        lines = record.proposal["lines"]
        subtotal = sum(line["subtotal_cents"] for line in lines)
        total = record.proposal["total_cents"]
        if total <= 0 or (order.payment_change_for and order.payment_change_for * 100 < total):
            raise McpToolError("invalid_payment", "A alteração exige nova análise do pagamento.")
        db.query(OrderItem).filter_by(tenant_id=order.tenant_id, order_id=order.id).delete(synchronize_session="fetch")
        create_order_items(db, order.tenant_id, order.id, lines)
        order.itens = _build_items_text(lines)
        order.items_json = json.dumps(lines, ensure_ascii=False)
        order.subtotal = Decimal(subtotal) / 100
        order.delivery_fee = Decimal(record.proposal["fee_cents"]) / 100
        order.total_cents = order.valor_total = payment.amount_cents = total
    db.flush()
    enqueue_wazza_order_mutation(db, order, record)
    record.state = "applied"
    record.resolved_by = user_id
    record.resolved_at = datetime.now(timezone.utc)
    record.evidence = {"order_id": order.id, "order_status": canonical_status(order.status),
                       "payments": [[payment.id, payment.status]], "source": "transaction"}


def _signature(identity, tenant_id, order_id, action, proposal, expiry):
    message = ["wazza-order-mutation-v1", tenant_id, identity.phone, identity.conversation_id,
               order_id, action, proposal, expiry]
    return hmac.new(config.JWT_SECRET_KEY.encode(), _encode(message), "sha256").hexdigest()


def _request(db, tenant_id, args, identity, action):
    query = _owned_orders_query(db, tenant_id, identity)
    if args.confirmation_token:
        order = _lock_order(db, query, tenant_id, args.order_id)
    else:
        order = query.filter(Order.id == args.order_id).first()
    if order is None:
        raise McpToolError("order_not_found", "Pedido não encontrado.")
    key = _digest([order.id, identity.phone, args.idempotency_key])
    payload_hash = _digest([action, args.model_dump(mode="json")])
    records = db.query(WazzaOrderMutation).filter_by(tenant_id=tenant_id, order_id=order.id)
    replay = records.filter_by(key_hash=key).one_or_none()
    if replay:
        if replay.request_hash != payload_hash:
            raise McpToolError("idempotency_conflict", "Chave reutilizada com outros dados.")
        return _receipt(replay)
    disposition = decide_customer_mutation(order.status, CustomerOrderAction(action)).disposition
    if disposition == MutationDisposition.DENIED:
        raise McpToolError("mutation_denied", "O estado atual do pedido bloqueia a solicitação.")
    items = [item.model_dump() for item in args.items] if action == "edit" else []
    proposal = _proposal(db, order, action, items)
    if not args.confirmation_token:
        expiry = int(time.time()) + 300
        signature = _signature(identity, tenant_id, order.id, action, proposal, expiry)
        return {"order_id": order.id, "action": action, "before_cents": order.total_cents,
                "after_cents": proposal["total_cents"], "items": proposal["lines"],
                "delivery_fee_cents": proposal["fee_cents"], "reason": proposal["reason"],
                "confirmation_token": f"{expiry}.{signature}", "confirmation_expires_at": expiry}
    timestamp, signature = args.confirmation_token.split(".")
    expiry = int(timestamp)
    if expiry <= time.time() or not hmac.compare_digest(
        signature, _signature(identity, tenant_id, order.id, action, proposal, expiry),
    ):
        raise McpToolError("quote_changed", "Solicite novo resumo e confirmação.")
    proposal_hash = _digest([action, proposal])
    existing = records.filter_by(proposal_hash=proposal_hash).one_or_none()
    if existing:
        return _receipt(existing)
    record = WazzaOrderMutation(
        tenant_id=tenant_id, order_id=order.id, key_hash=key, request_hash=payload_hash,
        proposal_hash=proposal_hash, action=action, state="pending_review", proposal=proposal,
        reason=proposal["reason"],
    )
    db.add(record)
    if record.reason == "customer_confirmed":
        _apply(db, order, record)
    db.flush()
    return _receipt(record)


def request_edit(db, tenant_id, args, identity):
    return _request(db, tenant_id, args, identity, "edit")


def request_cancel(db, tenant_id, args, identity):
    return _request(db, tenant_id, args, identity, "cancel")


def _receipt(record):
    return {"request_id": record.id, "order_id": record.order_id, "action": record.action, "state": record.state}


def _iso_utc(timestamp):
    if timestamp is None:
        return None
    return (timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp).isoformat()


def queue_item(record):
    return {
        **_receipt(record), "reason": record.reason, "before_cents": record.proposal["before"]["total_cents"],
        "before_status": record.proposal["before"]["status"],
        "after_cents": record.proposal["total_cents"], "before_items": record.proposal["before"]["lines"],
        "after_items": record.proposal["lines"], "created_at": _iso_utc(record.created_at),
        "decided_by": record.decided_by, "decided_at": _iso_utc(record.decided_at),
        "resolved_by": record.resolved_by, "resolved_at": _iso_utc(record.resolved_at),
        "decision_reason": record.decision_reason, "resolution_reason": record.resolution_reason,
        "evidence": record.evidence,
    }


def _verify_cancelled_effects(db, order):
    if order.coupon_id or order.discount_amount or db.query(CouponRedemption.id).filter_by(order_id=order.id).first():
        return False
    filters = {"tenant_id": order.tenant_id, "order_id": order.id}
    points = defaultdict(int)
    for entry in db.query(CustomerPointTransaction).filter_by(**filters):
        points[entry.customer_id] += entry.points_delta
    stock = defaultdict(float)
    for movement in db.query(InventoryMovement).filter_by(**filters):
        if movement.type not in {"IN", "OUT"}:
            return False
        stock[movement.inventory_item_id] += movement.quantity * (1 if movement.type == "IN" else -1)
    return not any(points.values()) and all(abs(quantity) < 1e-6 for quantity in stock.values())


def _verify(db, order, record):
    payments = _payments(db, order)
    original = {payment[0] for payment in record.proposal["before"]["payments"]}
    if (
        not payments or not original <= {payment.id for payment in payments} or _native(db, order)
        or order.assigned_delivery_user_id or order.ready_at or order.start_delivery_at
    ):
        return False
    status = canonical_status(order.status)
    if record.action == "cancel":
        return (
            status in CANCELED and _verify_cancelled_effects(db, order)
            and all(
                (payment.status == "canceled" and payment.paid_at is None
                 and not db.query(CashMovement.id).filter_by(
                     tenant_id=order.tenant_id, reference_type="order_payment", reference_id=payment.id,
                 ).first())
                or payment.status == "refunded" and payment.paid_at is not None
                and db.query(CashMovement.id).filter_by(
                    tenant_id=order.tenant_id, reference_type="order_payment",
                    reference_id=payment.id, type="out", category="refund", amount_cents=payment.amount_cents,
                ).first() is not None
                for payment in payments
            )
        )
    return (
        status == record.proposal["before"]["status"]
        and status in ALLOWED
        and _digest([order.order_type, order.delivery_address_json]) == record.proposal["before"]["fulfillment_hash"]
        and order.total_cents == order.valor_total == record.proposal["total_cents"]
        and _money_cents(order.delivery_fee) == record.proposal["fee_cents"]
        and _current_lines(db, order) == _compact(record.proposal["lines"])
        and _manual_pending(db, order, payments) is not None
        and not _effects(db, order)
    )


def decide(db, tenant_id, user_id, request_id, action, reason):
    query = db.query(WazzaOrderMutation).filter_by(tenant_id=tenant_id, id=request_id)
    record = query.first()
    if record is None:
        raise HTTPException(404, "Solicitação não encontrada.")
    order = _lock_order(db, db.query(Order).filter_by(tenant_id=tenant_id), tenant_id, record.order_id)
    record = query.populate_existing().with_for_update().one()
    expected = "manual_resolution" if action == "verify" else "pending_review"
    if record.state != expected:
        if (action == "reject" and record.state == "rejected"
            or action == "approve" and record.decided_by and record.state in {"manual_resolution", "applied", "failed"}
            or action == "verify" and record.resolved_by and record.state in {"applied", "failed"}):
            return queue_item(record)
        raise HTTPException(409, "Solicitação fora do estado esperado.")
    previous = record.state
    now = datetime.now(timezone.utc)
    if action == "verify":
        record.resolved_by = user_id
        record.resolved_at = now
        record.resolution_reason = reason
        record.state = "applied" if _verify(db, order, record) else "failed"
        if record.state == "applied":
            enqueue_wazza_order_mutation(db, order, record)
        record.evidence = {"order_id": order.id, "order_status": canonical_status(order.status),
                           "payments": [[p.id, p.status] for p in _payments(db, order)], "source": "verification"}
    else:
        record.decided_by = user_id
        record.decided_at = now
        record.decision_reason = reason
        if action == "reject":
            record.state = "rejected"
        elif canonical_status(order.status) not in ALLOWED:
            record.state = "failed"
        else:
            try:
                with db.begin_nested():
                    proposal = _proposal(db, order, record.action, record.proposal["items"])
                    if proposal != record.proposal:
                        record.state = "failed"
                    elif _can_apply(db, order, _payments(db, order)):
                        _apply(db, order, record, user_id)
                    else:
                        record.state = "manual_resolution"
            except (McpToolError, HTTPException, ValueError):
                record.state = "failed"
    log_admin_action(
        db, tenant_id=tenant_id, user_id=user_id, action=f"wazza_order_{action}",
        entity_type="wazza_order_mutation", entity_id=record.id,
        meta={"order_id": order.id, "from_state": previous, "to_state": record.state,
              "order_status": canonical_status(order.status)},
    )
    db.flush()
    return queue_item(record)
