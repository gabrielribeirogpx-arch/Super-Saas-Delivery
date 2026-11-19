"""Stripe subscription checkout. The provider webhook is the only activation source."""
from datetime import datetime, timezone

import requests

from app.models.plan import Plan
from app.models.plan_entitlement import PlanEntitlement
from app.models.subscription import Subscription, SubscriptionStatus as Status
from app.services.billing_common import BillingError, utc


def stripe_request(settings, method, path, *, data=None, idempotency_key=None):
    headers = {"Authorization": f"Bearer {settings.secret_key}", "Stripe-Version": "2025-02-24.acacia"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    try:
        response = requests.request(method, "https://api.stripe.com/v1/" + path,
            headers=headers, params=data if method == "GET" else None,
            data=data if method != "GET" else None, timeout=15)
        value = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise BillingError("stripe_unavailable") from exc
    if not response.ok or not isinstance(value, dict):
        raise BillingError("stripe_api_error")
    return value


class StripeBilling:
    def __init__(self, db, settings):
        self.db, self.settings = db, settings

    def offers(self):
        result = []
        if not self.settings.enabled:
            return result
        for offer in self.settings.offers:
            plan = self.db.query(Plan).filter_by(code=offer.plan_code, active=True).one_or_none()
            if plan is None:
                continue
            features = self.db.query(PlanEntitlement).filter_by(plan_id=plan.id).order_by(PlanEntitlement.feature_code).all()
            result.append(dict(code=plan.code, name=plan.name, price_cents=offer.price_cents,
                features=[dict(code=f.feature_code, enabled=f.enabled, limit=f.limit_value) for f in features]))
        return result

    def summary(self, user):
        sub = self.db.query(Subscription).filter_by(tenant_id=user.tenant_id).one_or_none()
        plan = self.db.get(Plan, sub.plan_id) if sub else None
        now = datetime.now(timezone.utc)
        end = utc(sub.current_period_end) if sub and sub.current_period_end else None
        return dict(enabled=self.settings.enabled, provider=sub.provider if sub else None,
            status=("expired" if sub and sub.status == Status.ACTIVE and end and end <= now else sub.status.value if sub else "not_contracted"),
            plan_name=plan.name if plan else None, period_end=end,
            cancel_at_period_end=bool(sub and sub.cancel_at_period_end), cancel_pending=False,
            can_cancel=bool(self.settings.enabled and sub and sub.provider == "stripe" and sub.provider_subscription_id
                and sub.status in {Status.ACTIVE, Status.PAST_DUE} and not sub.cancel_at_period_end),
            can_checkout=bool(self.settings.enabled and sub and sub.provider == "stripe"
                and sub.status in {Status.INACTIVE, Status.CANCELED, Status.EXPIRED}),
            checkout_pending=bool(sub and sub.provider == "stripe" and sub.status == Status.INACTIVE
                and sub.provider_subscription_id), offers=self.offers(), events=[])

    def checkout(self, user, plan_code):
        if not self.settings.enabled:
            raise BillingError("stripe_disabled")
        offer = next((o for o in self.settings.offers if o.plan_code == plan_code), None)
        plan = self.db.query(Plan).filter_by(code=plan_code, active=True).one_or_none()
        if offer is None or plan is None:
            raise BillingError("plan_not_available")
        sub = self.db.query(Subscription).filter_by(tenant_id=user.tenant_id).with_for_update().one_or_none()
        if sub is None or sub.provider != "stripe" or sub.status not in {Status.INACTIVE, Status.CANCELED, Status.EXPIRED}:
            raise BillingError("existing_subscription_requires_migration")
        previous_id = sub.provider_subscription_id
        if sub.provider_subscription_id:
            remote = stripe_request(self.settings, "GET", "subscriptions/" + sub.provider_subscription_id,
                data={"expand[]": "latest_invoice.confirmation_secret"})
            if remote.get("status") in {"incomplete_expired", "canceled"}:
                sub.provider_subscription_id = None
            elif remote.get("status") != "incomplete" or remote["items"]["data"][0]["price"]["id"] != offer.price_id:
                raise BillingError("checkout_already_started")
            else:
                return self._checkout_secret(remote, offer)
        price = stripe_request(self.settings, "GET", "prices/" + offer.price_id)
        if (not price.get("active") or price.get("currency") != "brl"
            or price.get("unit_amount") != offer.price_cents
            or (price.get("recurring") or {}).get("interval") != "month"
            or (price.get("recurring") or {}).get("interval_count") != 1):
            raise BillingError("stripe_price_mismatch")
        customer = ({"id": sub.provider_customer_id} if sub.provider_customer_id else
            stripe_request(self.settings, "POST", "customers",
                data={"email": user.email, "metadata[tenant_id]": str(user.tenant_id)},
                idempotency_key=f"fomizero-customer-{user.tenant_id}"))
        remote = stripe_request(self.settings, "POST", "subscriptions",
            data={"customer": customer["id"], "items[0][price]": offer.price_id,
                "payment_behavior": "default_incomplete",
                "payment_settings[save_default_payment_method]": "on_subscription",
                "metadata[tenant_id]": str(user.tenant_id),
                "expand[]": "latest_invoice.confirmation_secret"},
            idempotency_key=f"fomizero-subscription-{user.tenant_id}-{offer.price_id}-{previous_id or 'initial'}")
        if remote.get("status") not in {"incomplete", "active"}:
            raise BillingError("stripe_subscription_unavailable")
        sub.plan_id = plan.id
        sub.provider_customer_id = customer["id"]
        sub.provider_subscription_id = remote["id"]
        self.db.flush()
        return self._checkout_secret(remote, offer)

    def _checkout_secret(self, remote, offer):
        secret = ((remote.get("latest_invoice") or {}).get("confirmation_secret") or {}).get("client_secret")
        if not secret:
            raise BillingError("stripe_payment_secret_unavailable")
        return dict(client_secret=secret, publishable_key=self.settings.publishable_key,
            plan_code=offer.plan_code, price_cents=offer.price_cents)

    def cancel(self, user):
        sub = self.db.query(Subscription).filter_by(tenant_id=user.tenant_id).with_for_update().one_or_none()
        if not sub or sub.provider != "stripe" or not sub.provider_subscription_id or sub.cancel_at_period_end:
            raise BillingError("stripe_subscription_not_cancelable")
        stripe_request(self.settings, "POST", "subscriptions/" + sub.provider_subscription_id,
            data={"cancel_at_period_end": "true"},
            idempotency_key=f"fomizero-cancel-{sub.provider_subscription_id}")
        # Webhook applies the authoritative state.
