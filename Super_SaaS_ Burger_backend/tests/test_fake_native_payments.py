from dataclasses import replace

import pytest

from app.services.commercial_policy import (
    CommercialContext, FeeRule, OrderAmounts, PaymentMethod,
    PlanCode, SalesChannel, quote_payment,
)
from app.services.fake_native_payments import (
    FakeNativePaymentProvider, FakePaymentEvent, PaymentState, SettlementState,
)


def quote(tenant_id=1, order_id=1, total=10_000):
    context = CommercialContext(tenant_id, PlanCode.FREE, SalesChannel.OWN_STORE)
    rule = FeeRule("fixture-only", PlanCode.FREE, SalesChannel.OWN_STORE, PaymentMethod.NATIVE_PIX, 200, 20)
    return quote_payment(context, order_id, OrderAmounts(total), rule)


def event(intent, desired_state, event_id="evt-1", **changes):
    values = dict(
        event_id=event_id, payment_id=intent.payment_id,
        tenant_id=intent.quote.context.tenant_id,
        amount_cents=intent.quote.amounts.total_cents,
        state=desired_state,
    )
    values.update(changes)
    return FakePaymentEvent(**values)


def test_creation_selects_method_but_does_not_confirm_receipt_or_settlement():
    provider = FakeNativePaymentProvider()
    intent = provider.create(quote(), "request-1")
    assert intent.payment_id.startswith("fake_")
    assert intent.state is PaymentState.PENDING
    assert intent.settlement_state is SettlementState.NOT_SETTLED
    assert provider.ledger_for_tenant(1) == ()


def test_creation_retry_is_idempotent_but_changed_payload_is_rejected():
    provider = FakeNativePaymentProvider()
    original = provider.create(quote(), "request-1")
    assert provider.create(quote(), "request-1") == original
    with pytest.raises(ValueError, match="idempotency_conflict"):
        provider.create(quote(total=11_000), "request-1")
    with pytest.raises(ValueError, match="order_already_has_intent"):
        provider.create(quote(), "another-key")


@pytest.mark.parametrize("changes", [
    {"platform_fee_cents": 0}, {"merchant_before_psp_cents": 10_000},
    {"fee_base_cents": 0}, {"currency": "USD"},
])
def test_edited_snapshot_does_not_change_fee_or_currency(changes):
    provider = FakeNativePaymentProvider()
    with pytest.raises(ValueError, match="invalid_quote_snapshot"):
        provider.create(replace(quote(), **changes), "request-1")
    assert provider.ledger_for_tenant(1) == ()


def test_idempotency_keys_order_ids_and_ledger_are_tenant_scoped():
    provider = FakeNativePaymentProvider()
    first = provider.create(quote(1), "same-key")
    second = provider.create(quote(2), "same-key")
    assert first.payment_id != second.payment_id
    with pytest.raises(ValueError, match="payment_not_found"):
        provider.get(2, first.payment_id)
    with pytest.raises(ValueError, match="payment_not_found"):
        provider.apply_event(event(first, PaymentState.PAID, tenant_id=2))
    provider.apply_event(event(first, PaymentState.PAID))
    assert len(provider.ledger_for_tenant(1)) == 1
    assert provider.ledger_for_tenant(2) == ()
    assert provider.get(2, second.payment_id).state is PaymentState.PENDING


def test_paid_event_books_exact_split_once_and_does_not_settle():
    provider = FakeNativePaymentProvider()
    intent = provider.create(quote(), "request-1")
    approved = provider.apply_event(event(intent, PaymentState.PAID))
    provider.apply_event(event(intent, PaymentState.PAID))
    provider.apply_event(event(intent, PaymentState.PAID, event_id="same-state-new-id"))
    assert approved.state is PaymentState.PAID
    assert approved.settlement_state is SettlementState.NOT_SETTLED
    entries = provider.ledger_for_tenant(1)
    assert len(entries) == 1
    assert entries[0].gross_delta_cents == 10_000
    assert entries[0].platform_fee_delta_cents == 220
    assert entries[0].merchant_before_psp_delta_cents == 9_780


def test_wrong_amount_and_unknown_currency_cannot_confirm_payment():
    provider = FakeNativePaymentProvider()
    intent = provider.create(quote(), "request-1")
    with pytest.raises(ValueError, match="payment_amount_mismatch"):
        provider.apply_event(event(intent, PaymentState.PAID, amount_cents=9_999))
    with pytest.raises(ValueError, match="unsupported_currency"):
        event(intent, PaymentState.PAID, currency="USD")
    assert provider.get(1, intent.payment_id).state is PaymentState.PENDING
    assert provider.ledger_for_tenant(1) == ()


def test_event_id_cannot_be_reused_for_another_payment():
    provider = FakeNativePaymentProvider()
    first = provider.create(quote(order_id=1), "first")
    second = provider.create(quote(order_id=2), "second")
    provider.apply_event(event(first, PaymentState.PAID, "same-event"))
    with pytest.raises(ValueError, match="event_id_conflict"):
        provider.apply_event(event(second, PaymentState.PAID, "same-event"))
    assert provider.get(1, second.payment_id).state is PaymentState.PENDING


def test_full_refund_reverses_balances_once_and_old_paid_replay_does_not_resurrect():
    provider = FakeNativePaymentProvider()
    intent = provider.create(quote(), "request-1")
    paid_event = event(intent, PaymentState.PAID, "paid")
    provider.apply_event(paid_event)
    refund = event(intent, PaymentState.REFUNDED, "refund")
    provider.apply_event(refund)
    provider.apply_event(refund)
    provider.apply_event(event(intent, PaymentState.REFUNDED, "refund-again"))
    assert provider.apply_event(paid_event).state is PaymentState.REFUNDED
    entries = provider.ledger_for_tenant(1)
    assert len(entries) == 2
    assert sum(e.gross_delta_cents for e in entries) == 0
    assert sum(e.platform_fee_delta_cents for e in entries) == 0
    assert sum(e.merchant_before_psp_delta_cents for e in entries) == 0
    with pytest.raises(ValueError, match="invalid_payment_transition"):
        provider.apply_event(event(intent, PaymentState.PAID, "late-paid"))


@pytest.mark.parametrize("terminal", [PaymentState.FAILED, PaymentState.CANCELED])
def test_failed_and_canceled_intents_do_not_book_money_or_later_become_paid(terminal):
    provider = FakeNativePaymentProvider()
    intent = provider.create(quote(), "request-1")
    provider.apply_event(event(intent, terminal))
    assert provider.ledger_for_tenant(1) == ()
    with pytest.raises(ValueError, match="invalid_payment_transition"):
        provider.apply_event(event(intent, PaymentState.PAID, "late-paid"))


def test_refund_before_receipt_is_rejected():
    provider = FakeNativePaymentProvider()
    intent = provider.create(quote(), "request-1")
    with pytest.raises(ValueError, match="invalid_payment_transition"):
        provider.apply_event(event(intent, PaymentState.REFUNDED))
    assert provider.ledger_for_tenant(1) == ()


@pytest.mark.parametrize("changes", [
    {"event_id": ""}, {"payment_id": ""}, {"tenant_id": True},
    {"amount_cents": True}, {"amount_cents": -1},
    {"state": "paid"}, {"state": PaymentState.PENDING},
])
def test_malformed_fake_events_are_rejected(changes):
    provider = FakeNativePaymentProvider()
    intent = provider.create(quote(), "request-1")
    with pytest.raises(ValueError):
        event(intent, PaymentState.PAID, **changes)


def test_fake_provider_rejects_a_manual_payment_even_for_a_monthly_store():
    ctx = CommercialContext(1, PlanCode.ESSENTIAL, SalesChannel.OWN_STORE, True)
    rule = FeeRule("fixture-only", PlanCode.ESSENTIAL, SalesChannel.OWN_STORE, PaymentMethod.CASH, 0, 0)
    snapshot = quote_payment(ctx, 1, OrderAmounts(1_000), rule)
    with pytest.raises(ValueError, match="native_payment_required"):
        FakeNativePaymentProvider().create(snapshot, "request-1")
