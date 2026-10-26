"""In-memory test adapter: no HTTP, PSP credentials, persistence or real funds.

Fake events are simulation commands, not verified production webhooks. Never
expose this adapter through a public/payment endpoint or use it for real orders.
"""
from dataclasses import dataclass, replace
from enum import Enum
from uuid import uuid4

from app.services.commercial_policy import (
    NATIVE_METHODS, PaymentQuote, _identifier, _integer, quote_payment,
)


class PaymentState(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class SettlementState(str, Enum):
    NOT_SETTLED = "not_settled"


@dataclass(frozen=True)
class FakePaymentIntent:
    payment_id: str
    quote: PaymentQuote
    state: PaymentState = PaymentState.PENDING
    settlement_state: SettlementState = SettlementState.NOT_SETTLED


@dataclass(frozen=True)
class FakePaymentEvent:
    event_id: str
    payment_id: str
    tenant_id: int
    amount_cents: int
    state: PaymentState
    currency: str = "BRL"

    def __post_init__(self) -> None:
        _identifier(self.event_id, "invalid_event_id")
        _identifier(self.payment_id, "invalid_payment_id")
        _integer(self.tenant_id, "invalid_tenant", 1)
        _integer(self.amount_cents, "invalid_event_amount", 1)
        if not isinstance(self.state, PaymentState) or self.state is PaymentState.PENDING:
            raise ValueError("invalid_event_state")
        if self.currency != "BRL":
            raise ValueError("unsupported_currency")


@dataclass(frozen=True)
class SimulatedLedgerEntry:
    tenant_id: int
    payment_id: str
    event_id: str
    gross_delta_cents: int
    platform_fee_delta_cents: int
    merchant_before_psp_delta_cents: int


_TRANSITIONS = {
    PaymentState.PENDING: frozenset({
        PaymentState.PAID, PaymentState.FAILED, PaymentState.CANCELED,
    }),
    PaymentState.PAID: frozenset({PaymentState.REFUNDED}),
    PaymentState.FAILED: frozenset(),
    PaymentState.CANCELED: frozenset(),
    PaymentState.REFUNDED: frozenset(),
}


class FakeNativePaymentProvider:
    """Single-process test double. Not durable and not concurrency-safe.

    One intent per tenant/order in this first slice. Failed/canceled attempt
    retries, partial refunds and real settlement belong to the persistent PSP
    integration, not this fake. Every ledger entry is simulated.
    """

    def __init__(self) -> None:
        self._intents: dict[str, FakePaymentIntent] = {}
        self._keys: dict[tuple[int, str], str] = {}
        self._orders: dict[tuple[int, int], str] = {}
        self._events: dict[tuple[int, str], FakePaymentEvent] = {}
        self._ledger: list[SimulatedLedgerEntry] = []

    def create(self, quote: PaymentQuote, idempotency_key: str) -> FakePaymentIntent:
        _identifier(idempotency_key, "invalid_idempotency_key")
        # Recompute instead of accepting edited fee/total fields.
        expected = quote_payment(quote.context, quote.order_id, quote.amounts, quote.rule)
        if expected != quote or quote.currency != "BRL":
            raise ValueError("invalid_quote_snapshot")
        if quote.rule.payment_method not in NATIVE_METHODS:
            raise ValueError("native_payment_required")
        tenant_id = quote.context.tenant_id
        key = (tenant_id, idempotency_key)
        existing_id = self._keys.get(key)
        if existing_id:
            intent = self._intents[existing_id]
            if intent.quote != quote:
                raise ValueError("idempotency_conflict")
            return intent
        order_key = (tenant_id, quote.order_id)
        if order_key in self._orders:
            raise ValueError("order_already_has_intent")
        intent = FakePaymentIntent(payment_id=f"fake_{uuid4().hex}", quote=quote)
        self._intents[intent.payment_id] = intent
        self._keys[key] = intent.payment_id
        self._orders[order_key] = intent.payment_id
        return intent

    def get(self, tenant_id: int, payment_id: str) -> FakePaymentIntent:
        _integer(tenant_id, "invalid_tenant", 1)
        intent = self._intents.get(payment_id)
        if intent is None or intent.quote.context.tenant_id != tenant_id:
            raise ValueError("payment_not_found")
        return intent

    def apply_event(self, event: FakePaymentEvent) -> FakePaymentIntent:
        intent = self.get(event.tenant_id, event.payment_id)
        if event.amount_cents != intent.quote.amounts.total_cents:
            raise ValueError("payment_amount_mismatch")
        if event.currency != intent.quote.currency:
            raise ValueError("payment_currency_mismatch")
        key = (event.tenant_id, event.event_id)
        prior = self._events.get(key)
        if prior is not None:
            if prior != event:
                raise ValueError("event_id_conflict")
            # Replay returns current state, not a historical pre-refund state.
            return intent
        if event.state is not intent.state and event.state not in _TRANSITIONS[intent.state]:
            raise ValueError("invalid_payment_transition")
        changed = event.state is not intent.state
        updated = replace(intent, state=event.state)
        if changed and event.state in {PaymentState.PAID, PaymentState.REFUNDED}:
            sign = 1 if event.state is PaymentState.PAID else -1
            self._ledger.append(SimulatedLedgerEntry(
                tenant_id=event.tenant_id,
                payment_id=event.payment_id,
                event_id=event.event_id,
                gross_delta_cents=sign * intent.quote.amounts.total_cents,
                platform_fee_delta_cents=sign * intent.quote.platform_fee_cents,
                merchant_before_psp_delta_cents=sign * intent.quote.merchant_before_psp_cents,
            ))
        self._events[key] = event
        self._intents[event.payment_id] = updated
        return updated

    def ledger_for_tenant(self, tenant_id: int) -> tuple[SimulatedLedgerEntry, ...]:
        _integer(tenant_id, "invalid_tenant", 1)
        return tuple(entry for entry in self._ledger if entry.tenant_id == tenant_id)
