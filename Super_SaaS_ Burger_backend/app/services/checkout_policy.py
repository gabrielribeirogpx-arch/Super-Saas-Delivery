"""Opt-in checkout pilot. Native payments cannot be accepted without a PSP.

Never infer a Free plan or a paid subscription from request fields. Do not enable
this pilot for live stores or provision the commercial Free catalog yet.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import os
import unicodedata

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import ENV_NORMALIZED
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.commercial_policy import CommercialContext, PaymentMethod, PlanCode, SalesChannel, NATIVE_METHODS, evaluate_payment_policy

METHODS = {
    PaymentMethod.MANUAL_PIX: ("pix", "Pix direto da loja"),
    PaymentMethod.CASH: ("money", "Dinheiro"),
    PaymentMethod.EXTERNAL_CARD: ("card", "Cartão com a loja"),
    PaymentMethod.NATIVE_PIX: ("native_pix", "Pix online"),
    PaymentMethod.NATIVE_CARD: ("native_card", "Cartão online"),
}
ALIASES = {
    "pix": PaymentMethod.MANUAL_PIX, "manual_pix": PaymentMethod.MANUAL_PIX,
    "money": PaymentMethod.CASH, "cash": PaymentMethod.CASH, "dinheiro": PaymentMethod.CASH,
    "card": PaymentMethod.EXTERNAL_CARD, "external_card": PaymentMethod.EXTERNAL_CARD,
    "cartao": PaymentMethod.EXTERNAL_CARD, "credito": PaymentMethod.EXTERNAL_CARD, "debito": PaymentMethod.EXTERNAL_CARD,
    "credit_card": PaymentMethod.EXTERNAL_CARD, "debit_card": PaymentMethod.EXTERNAL_CARD,
    "native_pix": PaymentMethod.NATIVE_PIX, "native_card": PaymentMethod.NATIVE_CARD,
}


def payment_method(raw: str) -> PaymentMethod | None:
    value = ''.join(c for c in unicodedata.normalize('NFKD', str(raw or '').strip().lower()) if not unicodedata.combining(c))
    return ALIASES.get(value)


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


@dataclass(frozen=True)
class CheckoutPolicy:
    enforced: bool
    context: CommercialContext | None
    reason: str

    def public_payload(self) -> dict:
        options = []
        for method, (id, label) in METHODS.items():
            if not self.enforced:
                if method in NATIVE_METHODS:
                    continue
                allowed = True
            elif self.context is None:
                continue
            else:
                allowed = evaluate_payment_policy(self.context, method).allowed
            if allowed:
                options.append({"id": id, "label": label, "available": method not in NATIVE_METHODS})
        available = any(option['available'] for option in options)
        return {"methods": options, "message": None if available else "Esta loja não está recebendo pedidos online no momento."}


def resolve_checkout_policy(db: Session, tenant_id: int, *, for_write=False, now=None) -> CheckoutPolicy:
    enabled = os.getenv('CHECKOUT_POLICY_ENABLED', '').lower() in {'1', 'true', 'yes'}
    if not enabled:
        return CheckoutPolicy(False, None, 'legacy')
    try:
        ids = {int(item.strip()) for item in os.getenv('CHECKOUT_POLICY_TENANT_IDS', '').split(',') if item.strip()}
        if not ids or any(id <= 0 for id in ids):
            raise ValueError()
    except ValueError:
        return CheckoutPolicy(True, None, 'invalid_pilot_configuration')
    if tenant_id not in ids:
        return CheckoutPolicy(False, None, 'legacy')
    if ENV_NORMALIZED not in {'test', 'staging', 'stage', 'homolog'}:
        return CheckoutPolicy(True, None, 'pilot_environment_required')
    now = _utc(now or datetime.now(timezone.utc))
    query = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).populate_existing()
    subscription = (query.with_for_update(read=True) if for_write else query).one_or_none()
    if subscription is None:
        return CheckoutPolicy(True, None, 'commercial_assignment_missing')
    query = db.query(Plan).filter(Plan.id == subscription.plan_id).populate_existing()
    plan = (query.with_for_update(read=True) if for_write else query).one_or_none()
    if plan is None or not plan.active:
        return CheckoutPolicy(True, None, 'plan_inactive')
    try:
        code = PlanCode(plan.code)
    except ValueError:
        return CheckoutPolicy(True, None, 'unknown_plan')
    if subscription.status != SubscriptionStatus.ACTIVE:
        return CheckoutPolicy(True, None, 'subscription_not_active')
    start, end = _utc(subscription.current_period_start), _utc(subscription.current_period_end)
    if (start and start > now) or (end and end <= now) or (code != PlanCode.FREE and end is None):
        return CheckoutPolicy(True, None, 'subscription_period_invalid')
    return CheckoutPolicy(True, CommercialContext(tenant_id, code, SalesChannel.OWN_STORE, True), 'allowed')


def enforce_checkout_payment(db: Session, tenant_id: int, raw: str) -> CheckoutPolicy:
    policy = resolve_checkout_policy(db, tenant_id, for_write=True)
    method = payment_method(raw)
    if policy.enforced:
        if policy.context is None:
            raise HTTPException(status_code=409, detail='Esta loja não está recebendo pedidos online no momento.')
        if method is None:
            raise HTTPException(status_code=422, detail='Selecione uma forma de pagamento disponível.')
        decision = evaluate_payment_policy(policy.context, method)
        if not decision.allowed:
            raise HTTPException(status_code=422, detail='Esta forma de pagamento não está disponível para esta loja.')
    # Always reject explicit native IDs, including callers outside the pilot.
    # Neither the legacy auto-paid helper nor the sandbox store is a real PSP.
    if method in NATIVE_METHODS:
        raise HTTPException(status_code=503, detail='Pagamento online temporariamente indisponível. Nenhuma cobrança foi realizada.')
    return policy
