"""Pure commercial rules. No routes, catalog seed, enforcement or live charges.

Contexts and fee rules must come from trusted server-side state, never checkout
input. This module deliberately supplies no production price/default plan.
"""
from dataclasses import dataclass
from enum import Enum


class PlanCode(str, Enum):
    FREE = "free"
    ESSENTIAL = "essential"
    OPERATION = "operation"
    PRO = "pro"


class SalesChannel(str, Enum):
    OWN_STORE = "own_store"
    MARKETPLACE = "marketplace"


class PaymentMethod(str, Enum):
    NATIVE_PIX = "native_pix"
    NATIVE_CARD = "native_card"
    CASH = "cash"
    EXTERNAL_CARD = "external_card"
    MANUAL_PIX = "manual_pix"


NATIVE_METHODS = frozenset({PaymentMethod.NATIVE_PIX, PaymentMethod.NATIVE_CARD})


def _integer(value: int, code: str, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(code)


def _identifier(value: str, code: str) -> None:
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > 120:
        raise ValueError(code)


def _member(value: Enum, enum_type: type[Enum], code: str) -> None:
    if not isinstance(value, enum_type):
        raise ValueError(code)


@dataclass(frozen=True)
class CommercialContext:
    tenant_id: int
    plan_code: PlanCode
    channel: SalesChannel
    subscription_active: bool = False

    def __post_init__(self) -> None:
        _integer(self.tenant_id, "invalid_tenant", 1)
        _member(self.plan_code, PlanCode, "unknown_plan")
        _member(self.channel, SalesChannel, "unknown_channel")
        if type(self.subscription_active) is not bool:
            raise ValueError("invalid_subscription_state")


@dataclass(frozen=True)
class PaymentPolicyDecision:
    allowed: bool
    reason: str
    native_required: bool


def evaluate_payment_policy(
    context: CommercialContext, method: PaymentMethod,
) -> PaymentPolicyDecision:
    """Observe a proposed policy; existing checkout routes do not call this."""
    _member(method, PaymentMethod, "unknown_payment_method")
    native_required = (
        context.plan_code is PlanCode.FREE
        or context.channel is SalesChannel.MARKETPLACE
    )
    if context.plan_code is not PlanCode.FREE and not context.subscription_active:
        return PaymentPolicyDecision(False, "subscription_not_active", native_required)
    if native_required and method not in NATIVE_METHODS:
        return PaymentPolicyDecision(False, "native_payment_required", True)
    return PaymentPolicyDecision(True, "allowed", native_required)


@dataclass(frozen=True)
class OrderAmounts:
    subtotal_cents: int
    discount_cents: int = 0
    delivery_cents: int = 0

    def __post_init__(self) -> None:
        _integer(self.subtotal_cents, "invalid_subtotal")
        _integer(self.discount_cents, "invalid_discount")
        _integer(self.delivery_cents, "invalid_delivery")
        if self.discount_cents > self.subtotal_cents:
            raise ValueError("discount_exceeds_subtotal")
        if self.total_cents <= 0:
            raise ValueError("positive_total_required")

    @property
    def total_cents(self) -> int:
        return self.subtotal_cents - self.discount_cents + self.delivery_cents


@dataclass(frozen=True)
class FeeRule:
    version: str
    plan_code: PlanCode
    channel: SalesChannel
    payment_method: PaymentMethod
    rate_bps: int
    fixed_cents: int
    include_delivery: bool = False

    def __post_init__(self) -> None:
        _identifier(self.version, "invalid_fee_version")
        _member(self.plan_code, PlanCode, "unknown_plan")
        _member(self.channel, SalesChannel, "unknown_channel")
        _member(self.payment_method, PaymentMethod, "unknown_payment_method")
        _integer(self.rate_bps, "invalid_rate")
        _integer(self.fixed_cents, "invalid_fixed_fee")
        if self.rate_bps > 10_000:
            raise ValueError("invalid_rate")
        if type(self.include_delivery) is not bool:
            raise ValueError("invalid_delivery_fee_policy")


@dataclass(frozen=True)
class PaymentQuote:
    """Immutable order pricing snapshot; merchant value is before PSP costs.

    This is an internal value object, not a client-accepted payment payload.
    Actual settlement, taxes and courier compensation are outside this quote.
    """
    context: CommercialContext
    order_id: int
    amounts: OrderAmounts
    rule: FeeRule
    fee_base_cents: int
    platform_fee_cents: int
    merchant_before_psp_cents: int
    currency: str = "BRL"


def quote_payment(
    context: CommercialContext,
    order_id: int,
    amounts: OrderAmounts,
    rule: FeeRule,
) -> PaymentQuote:
    _integer(order_id, "invalid_order", 1)
    if context.plan_code is not rule.plan_code or context.channel is not rule.channel:
        raise ValueError("fee_rule_scope_mismatch")
    decision = evaluate_payment_policy(context, rule.payment_method)
    if not decision.allowed:
        raise ValueError(decision.reason)
    base = amounts.subtotal_cents - amounts.discount_cents
    if rule.include_delivery:
        base += amounts.delivery_cents
    # Integer half-up rounding; never binary floats for money.
    fee = (base * rule.rate_bps + 5_000) // 10_000 + rule.fixed_cents
    if fee > base:
        raise ValueError("fee_exceeds_base")
    if rule.payment_method not in NATIVE_METHODS and fee:
        raise ValueError("external_payment_commission_not_supported")
    return PaymentQuote(
        context=context,
        order_id=order_id,
        amounts=amounts,
        rule=rule,
        fee_base_cents=base,
        platform_fee_cents=fee,
        merchant_before_psp_cents=amounts.total_cents - fee,
    )
