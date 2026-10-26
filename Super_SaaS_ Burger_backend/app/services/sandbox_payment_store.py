"""Transactional persistence for simulations only, never a real PSP webhook API."""
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.finance import OrderPayment
from app.models.native_payment import (
    NativePaymentAttempt, NativePaymentEvent, NativePaymentIntent, NativePaymentLedger,
)
from app.models.order import Order
from app.services.commercial_policy import (
    CommercialContext, FeeRule, NATIVE_METHODS, OrderAmounts, PaymentMethod,
    PaymentQuote, PlanCode, SalesChannel, _identifier, _integer, quote_payment,
)
from app.services.fake_native_payments import FakePaymentEvent, PaymentState, _TRANSITIONS


def _payload(value) -> dict:
    return json.loads(json.dumps(asdict(value), sort_keys=True))


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _restore_quote(payload: dict) -> PaymentQuote:
    context = payload["context"]
    rule = payload["rule"]
    return quote_payment(
        CommercialContext(context["tenant_id"], PlanCode(context["plan_code"]),
                          SalesChannel(context["channel"]), context["subscription_active"]),
        payload["order_id"],
        OrderAmounts(**payload["amounts"]),
        FeeRule(rule["version"], PlanCode(rule["plan_code"]), SalesChannel(rule["channel"]),
                PaymentMethod(rule["payment_method"]), rule["rate_bps"], rule["fixed_cents"],
                rule["include_delivery"]),
    )


class SandboxPaymentStore:
    """Caller owns commit/rollback. Writes are sandbox simulation records only.

    runtime_environment and simulation_enabled must come from trusted runtime
    configuration, never from a consumer request. No router invokes this store.
    """

    def __init__(self, db: Session, *, runtime_environment: str, simulation_enabled: bool = False):
        if runtime_environment not in {"test", "staging"} or simulation_enabled is not True:
            raise ValueError("simulation_not_enabled")
        self.db = db

    def _ensure_outer_transaction(self) -> None:
        # Python sqlite3 may otherwise release an outermost SAVEPOINT as a commit.
        connection = self.db.connection()
        if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN")

    def get(self, tenant_id: int, public_id: str, *, lock: bool = False) -> NativePaymentIntent:
        _integer(tenant_id, "invalid_tenant", 1)
        _identifier(public_id, "invalid_payment_id")
        query = self.db.query(NativePaymentIntent).filter_by(tenant_id=tenant_id, public_id=public_id)
        if lock:
            query = query.populate_existing().with_for_update()
        intent = query.one_or_none()
        if intent is None:
            raise ValueError("payment_not_found")
        return intent

    def _by_key(self, tenant_id: int, key: str):
        attempt = self.db.query(NativePaymentAttempt).filter_by(tenant_id=tenant_id, idempotency_key=key).one_or_none()
        if attempt is None:
            return None
        return self.db.query(NativePaymentIntent).filter_by(id=attempt.intent_id, tenant_id=tenant_id).one()

    def _validate_snapshot(self, intent: NativePaymentIntent) -> PaymentQuote:
        try:
            quote = _restore_quote(intent.snapshot)
            expected = _payload(quote)
            valid = (
                _hash(expected) == intent.snapshot_hash
                and expected == intent.snapshot
                and quote.context.tenant_id == intent.tenant_id
                and quote.order_id == intent.order_id
                and quote.currency == intent.currency
                and quote.amounts.total_cents == intent.total_cents
                and quote.platform_fee_cents == intent.platform_fee_cents
                and quote.merchant_before_psp_cents == intent.merchant_before_psp_cents
            )
        except (KeyError, TypeError, ValueError):
            valid = False
        if not valid:
            raise ValueError("invalid_snapshot")
        return quote

    def create(
        self, context: CommercialContext, order_id: int, amounts: OrderAmounts,
        rule: FeeRule, idempotency_key: str,
    ) -> NativePaymentIntent:
        _identifier(idempotency_key, "invalid_idempotency_key")
        quote = quote_payment(context, order_id, amounts, rule)
        if rule.payment_method not in NATIVE_METHODS:
            raise ValueError("native_payment_required")
        self._ensure_outer_transaction()
        snapshot = _payload(quote)
        fingerprint = _hash(snapshot)
        order = self.db.query(Order).filter_by(id=order_id, tenant_id=context.tenant_id).populate_existing().with_for_update().one_or_none()
        if order is None:
            raise ValueError("order_not_found")
        if int(order.total_cents or order.valor_total or 0) != amounts.total_cents:
            raise ValueError("order_total_mismatch")
        prior = self._by_key(context.tenant_id, idempotency_key)
        if prior is not None:
            self._validate_snapshot(prior)
            if prior.snapshot_hash != fingerprint:
                raise ValueError("idempotency_conflict")
            return prior
        if self.db.query(NativePaymentIntent.id).filter_by(tenant_id=context.tenant_id, order_id=order_id).first():
            raise ValueError("order_already_has_intent")
        if self.db.query(OrderPayment.id).filter_by(tenant_id=context.tenant_id, order_id=order_id).first():
            raise ValueError("legacy_payment_exists")
        try:
            with self.db.begin_nested():
                intent = NativePaymentIntent(
                    tenant_id=context.tenant_id, order_id=order_id,
                    public_id=f"sim_{uuid4().hex}", snapshot=snapshot, snapshot_hash=fingerprint,
                    total_cents=amounts.total_cents, platform_fee_cents=quote.platform_fee_cents,
                    merchant_before_psp_cents=quote.merchant_before_psp_cents,
                )
                self.db.add(intent)
                self.db.flush()
                self.db.add(NativePaymentAttempt(
                    tenant_id=context.tenant_id, intent_id=intent.id, attempt_number=1,
                    idempotency_key=idempotency_key,
                ))
                self.db.flush()
            return intent
        except IntegrityError as exc:
            prior = self._by_key(context.tenant_id, idempotency_key)
            if prior is not None:
                self._validate_snapshot(prior)
                if prior.snapshot_hash == fingerprint:
                    return prior
            raise ValueError("payment_creation_conflict") from exc

    def apply_simulated_event(self, event: FakePaymentEvent) -> NativePaymentIntent:
        if not isinstance(event, FakePaymentEvent):
            raise ValueError("simulation_event_required")
        self._ensure_outer_transaction()
        intent = self.get(event.tenant_id, event.payment_id, lock=True)
        self._validate_snapshot(intent)
        if event.currency != intent.currency or event.amount_cents != intent.total_cents:
            raise ValueError("payment_amount_or_currency_mismatch")
        fingerprint = _hash(_payload(event))
        prior = self.db.query(NativePaymentEvent).filter_by(tenant_id=event.tenant_id, external_event_id=event.event_id).one_or_none()
        if prior is not None:
            if prior.payload_hash != fingerprint or prior.intent_id != intent.id:
                raise ValueError("event_id_conflict")
            return intent
        current = PaymentState(intent.status)
        if event.state is not current and event.state not in _TRANSITIONS[current]:
            raise ValueError("invalid_payment_transition")
        try:
            with self.db.begin_nested():
                record = NativePaymentEvent(
                    tenant_id=event.tenant_id, intent_id=intent.id,
                    external_event_id=event.event_id, payload_hash=fingerprint,
                    target_status=event.state.value, amount_cents=event.amount_cents, currency=event.currency,
                )
                self.db.add(record)
                self.db.flush()
                if event.state is not current:
                    # Load before changing status: query autoflush must not see
                    # paid/refunded without the timestamp required by the DB.
                    attempt = self.db.query(NativePaymentAttempt).filter_by(
                        tenant_id=event.tenant_id, intent_id=intent.id, attempt_number=1,
                    ).one()
                    if event.state is PaymentState.PAID:
                        intent.paid_at = datetime.now(timezone.utc)
                    if event.state is PaymentState.REFUNDED:
                        intent.refunded_at = datetime.now(timezone.utc)
                    intent.status = event.state.value
                    attempt.status = event.state.value
                    if event.state in {PaymentState.PAID, PaymentState.REFUNDED}:
                        sign = 1 if event.state is PaymentState.PAID else -1
                        self.db.add(NativePaymentLedger(
                            tenant_id=event.tenant_id, intent_id=intent.id, event_id=record.id,
                            kind="payment" if sign == 1 else "refund",
                            gross_delta_cents=sign * intent.total_cents,
                            platform_fee_delta_cents=sign * intent.platform_fee_cents,
                            merchant_delta_cents=sign * intent.merchant_before_psp_cents,
                        ))
                self.db.flush()
            return intent
        except IntegrityError as exc:
            prior = self.db.query(NativePaymentEvent).filter_by(tenant_id=event.tenant_id, external_event_id=event.event_id).one_or_none()
            if prior is not None and prior.payload_hash == fingerprint and prior.intent_id == intent.id:
                return self.get(event.tenant_id, event.payment_id, lock=True)
            raise ValueError("payment_event_conflict") from exc

    def ledger_for_tenant(self, tenant_id: int) -> tuple[NativePaymentLedger, ...]:
        _integer(tenant_id, "invalid_tenant", 1)
        return tuple(self.db.query(NativePaymentLedger).filter_by(tenant_id=tenant_id).order_by(NativePaymentLedger.id).all())
