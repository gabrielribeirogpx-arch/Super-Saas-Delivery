from dataclasses import FrozenInstanceError, replace

import pytest

from app.services.commercial_policy import (
    CommercialContext, FeeRule, NATIVE_METHODS, OrderAmounts, PaymentMethod,
    PlanCode, SalesChannel, evaluate_payment_policy, quote_payment,
)


def context(plan=PlanCode.FREE, channel=SalesChannel.OWN_STORE, active=False, tenant_id=1):
    return CommercialContext(tenant_id, plan, channel, active)


def rule(ctx, method=PaymentMethod.NATIVE_PIX, **overrides):
    values = dict(
        version="fixture-v1", plan_code=ctx.plan_code, channel=ctx.channel,
        payment_method=method, rate_bps=200, fixed_cents=30,
    )
    values.update(overrides)
    return FeeRule(**values)


@pytest.mark.parametrize("plan", list(PlanCode))
@pytest.mark.parametrize("channel", list(SalesChannel))
@pytest.mark.parametrize("method", list(PaymentMethod))
def test_payment_policy_matrix(plan, channel, method):
    ctx = context(plan, channel, active=plan is not PlanCode.FREE)
    decision = evaluate_payment_policy(ctx, method)
    required = plan is PlanCode.FREE or channel is SalesChannel.MARKETPLACE
    assert decision.native_required is required
    assert decision.allowed is (not required or method in NATIVE_METHODS)
    assert decision.reason == ("allowed" if decision.allowed else "native_payment_required")


@pytest.mark.parametrize("plan", [PlanCode.ESSENTIAL, PlanCode.OPERATION, PlanCode.PRO])
def test_inactive_monthly_subscription_does_not_receive_paid_policy(plan):
    decision = evaluate_payment_policy(context(plan), PaymentMethod.NATIVE_PIX)
    assert not decision.allowed
    assert decision.reason == "subscription_not_active"


def test_fee_uses_discounted_goods_and_preserves_delivery_by_default():
    ctx = context()
    amounts = OrderAmounts(subtotal_cents=10_000, discount_cents=1_500, delivery_cents=900)
    quote = quote_payment(ctx, 1, amounts, rule(ctx))
    assert quote.fee_base_cents == 8_500
    assert quote.platform_fee_cents == 200
    assert quote.merchant_before_psp_cents == 9_200
    assert quote.amounts.total_cents == 9_400
    assert quote.platform_fee_cents + quote.merchant_before_psp_cents == quote.amounts.total_cents
    assert quote.currency == "BRL"


def test_delivery_fee_base_requires_explicit_rule():
    ctx = context()
    quote = quote_payment(ctx, 1, OrderAmounts(10_000, 1_500, 900), rule(ctx, include_delivery=True))
    assert quote.fee_base_cents == 9_400
    assert quote.platform_fee_cents == 218
    assert quote.merchant_before_psp_cents == 9_182


def test_half_cent_rounding_is_integer_half_up():
    ctx = context()
    quote = quote_payment(ctx, 1, OrderAmounts(1), rule(ctx, rate_bps=5_000, fixed_cents=0))
    assert quote.platform_fee_cents == 1
    assert quote.merchant_before_psp_cents == 0


def test_plan_change_and_rule_revision_cannot_reprice_an_existing_quote():
    ctx = context()
    quote = quote_payment(ctx, 1, OrderAmounts(10_000), rule(ctx))
    paid = replace(ctx, plan_code=PlanCode.PRO, subscription_active=True)
    next_quote = quote_payment(paid, 2, OrderAmounts(10_000), rule(paid, version="fixture-v2", rate_bps=0, fixed_cents=0))
    assert next_quote.platform_fee_cents == 0
    assert quote.platform_fee_cents == 230
    assert quote.context.plan_code is PlanCode.FREE
    assert quote.rule.version == "fixture-v1"
    with pytest.raises(FrozenInstanceError):
        quote.platform_fee_cents = 0


@pytest.mark.parametrize("change", [
    {"plan_code": PlanCode.PRO},
    {"channel": SalesChannel.MARKETPLACE},
])
def test_fee_scope_cannot_be_reused_for_another_plan_or_channel(change):
    ctx = context()
    with pytest.raises(ValueError, match="fee_rule_scope_mismatch"):
        quote_payment(ctx, 1, OrderAmounts(1_000), replace(rule(ctx), **change))


@pytest.mark.parametrize("method", [PaymentMethod.CASH, PaymentMethod.MANUAL_PIX, PaymentMethod.EXTERNAL_CARD])
def test_free_cannot_quote_a_payment_bypass(method):
    ctx = context()
    with pytest.raises(ValueError, match="native_payment_required"):
        quote_payment(ctx, 1, OrderAmounts(1_000), rule(ctx, method, rate_bps=0, fixed_cents=0))


def test_monthly_own_channel_manual_payment_has_explicit_zero_platform_fee():
    ctx = context(PlanCode.ESSENTIAL, active=True)
    quote = quote_payment(ctx, 1, OrderAmounts(1_000), rule(ctx, PaymentMethod.CASH, rate_bps=0, fixed_cents=0))
    assert quote.platform_fee_cents == 0
    assert quote.merchant_before_psp_cents == 1_000
    with pytest.raises(ValueError, match="external_payment_commission_not_supported"):
        quote_payment(ctx, 2, OrderAmounts(1_000), rule(ctx, PaymentMethod.CASH))


@pytest.mark.parametrize("amounts", [
    {"subtotal_cents": True}, {"subtotal_cents": 10.5},
    {"subtotal_cents": "100"}, {"subtotal_cents": -1},
    {"subtotal_cents": 0}, {"subtotal_cents": 100, "discount_cents": 101},
    {"subtotal_cents": 100, "delivery_cents": -1},
    {"subtotal_cents": 100, "discount_cents": 100},
])
def test_invalid_money_is_rejected_without_coercion(amounts):
    with pytest.raises(ValueError):
        OrderAmounts(**amounts)


@pytest.mark.parametrize("changes", [
    {"rate_bps": True}, {"rate_bps": -1}, {"rate_bps": 10_001},
    {"rate_bps": 2.5}, {"fixed_cents": -1}, {"fixed_cents": "10"},
    {"version": ""}, {"version": " padded "}, {"include_delivery": 1},
])
def test_invalid_fee_rule_is_rejected(changes):
    with pytest.raises(ValueError):
        rule(context(), **changes)


def test_fee_cannot_make_the_commercial_base_negative():
    ctx = context()
    with pytest.raises(ValueError, match="fee_exceeds_base"):
        quote_payment(ctx, 1, OrderAmounts(10), rule(ctx, fixed_cents=100))


@pytest.mark.parametrize("tenant_id", [0, -1, True, "1"])
def test_invalid_tenant_context_is_rejected(tenant_id):
    with pytest.raises(ValueError, match="invalid_tenant"):
        context(tenant_id=tenant_id)


def test_unknown_or_unresolved_plan_and_channel_fail_closed():
    with pytest.raises(ValueError, match="unknown_plan"):
        CommercialContext(1, "free", SalesChannel.OWN_STORE)
    with pytest.raises(ValueError, match="unknown_plan"):
        CommercialContext(1, None, SalesChannel.OWN_STORE)
    with pytest.raises(ValueError, match="unknown_channel"):
        CommercialContext(1, PlanCode.FREE, "own_store")
    with pytest.raises(ValueError, match="unknown_payment_method"):
        evaluate_payment_policy(context(), "pix")
