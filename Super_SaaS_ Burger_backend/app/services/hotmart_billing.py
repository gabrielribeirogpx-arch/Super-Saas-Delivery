"""Authenticated subscription billing. No order payments or marketplace money here."""
from datetime import datetime, timedelta, timezone
import json
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from sqlalchemy import or_
from app.models.billing_checkout_intent import BillingCheckoutIntent, BillingIntentStatus as I
from app.models.billing_event import BillingEvent, BillingEventStatus as E, BillingVerificationStatus as V
from app.models.hotmart_subscription import HotmartSubscription
from app.models.plan import Plan
from app.models.plan_entitlement import PlanEntitlement
from app.models.subscription import Subscription, SubscriptionStatus as S
from app.models.tenant import Tenant
from app.services.admin_audit import log_admin_action
from app.services.billing_catalog import BillingCatalogService
from app.services.billing_common import BillingError, billing_transaction, utc
from app.services.hotmart_projection import EVENTS, validate_projection
from app.services.subscriptions import SubscriptionService, SubscriptionActor

PAID = {"PURCHASE_APPROVED", "PURCHASE_COMPLETE"}
REVOKED = {"PURCHASE_REFUNDED", "PURCHASE_CHARGEBACK"}

class HotmartBilling:
    def __init__(self, db, settings, *, clock=None):
        self.db, self.settings = db, settings
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _scope(self):
        return dict(account_id=self.settings.account_id, environment=self.settings.environment)

    def offers(self):
        result = []
        if not self.settings.enabled:
            return result
        for offer in self.settings.offers:
            plan = self.db.query(Plan).filter_by(code=offer.plan_code, active=True).one_or_none()
            if plan is None:
                continue
            try:
                self.mapping(offer.product_id, offer.plan_id)
            except BillingError:
                continue
            features = self.db.query(PlanEntitlement).filter_by(plan_id=plan.id).order_by(PlanEntitlement.feature_code).all()
            result.append(dict(code=plan.code, name=plan.name, price_cents=offer.price_cents,
                features=[dict(code=f.feature_code, enabled=f.enabled, limit=f.limit_value) for f in features]))
        return result

    def mapping(self, product, external_plan):
        return BillingCatalogService(self.db).resolve_mapping(provider="hotmart", environment=self.settings.environment,
            provider_account_id=self.settings.account_id, external_product_id=product, external_offer_id=external_plan)

    def checkout(self, user, plan_code):
        if not self.settings.enabled:
            raise BillingError("hotmart_disabled")
        tenant = self.db.query(Tenant).filter_by(id=user.tenant_id, is_active=True).with_for_update().one_or_none()
        if tenant is None:
            raise BillingError("tenant_unavailable")
        sub = self.db.query(Subscription).filter_by(tenant_id=user.tenant_id).one_or_none()
        pending_cancel = self.db.query(HotmartSubscription).filter_by(tenant_id=user.tenant_id,cancel_status="pending").first()
        if pending_cancel:
            raise BillingError("hotmart_cancellation_pending")
        now = self.clock()
        if sub is not None:
            if sub.provider != "hotmart":
                raise BillingError("existing_subscription_requires_migration")
            if sub.status not in {S.CANCELED, S.EXPIRED, S.INACTIVE}:
                raise BillingError("subscription_already_contracted")
        offer = next((o for o in self.settings.offers if o.plan_code == plan_code), None)
        if offer is None:
            raise BillingError("plan_not_available")
        mapping = self.mapping(offer.product_id, offer.plan_id)
        # Reuse a pending intent under the tenant lock; avoid duplicate subscriptions on double click.
        intent = self.db.query(BillingCheckoutIntent).filter_by(tenant_id=user.tenant_id, provider="hotmart",
            provider_account_id=self.settings.account_id, environment=self.settings.environment,
            plan_id=mapping.plan_id, status=I.PENDING).filter(BillingCheckoutIntent.expires_at > now).order_by(BillingCheckoutIntent.id.desc()).first()
        if sub is None:
            sub = SubscriptionService(self.db,clock=self.clock).create_subscription(user.tenant_id,mapping.plan_id,provider="hotmart")
        if intent is None:
            # Cancel other unused offers: one current contracting choice per store.
            self.db.query(BillingCheckoutIntent).filter_by(tenant_id=user.tenant_id, provider="hotmart", status=I.PENDING).update({"status": I.CANCELED})
            intent = BillingCatalogService(self.db).create_intent(user.tenant_id, mapping.plan_id, provider="hotmart",
                environment=self.settings.environment, provider_account_id=self.settings.account_id,
                expires_at=now + timedelta(days=7), now=now)
            log_admin_action(self.db, tenant_id=user.tenant_id, user_id=user.id, action="billing.checkout_started",
                entity_type="billing_checkout_intent", entity_id=intent.id, meta={"provider":"hotmart", "plan_id":mapping.plan_id})
        parts = urlsplit(offer.checkout_url)
        url = urlunsplit((parts.scheme, parts.netloc, parts.path,
            urlencode(parse_qsl(parts.query) + [("sck", intent.public_token)]), ""))
        return dict(checkout_url=url, expires_at=utc(intent.expires_at))

    def summary(self, user):
        sub = self.db.query(Subscription).filter_by(tenant_id=user.tenant_id).one_or_none()
        link = self.db.query(HotmartSubscription).filter_by(tenant_id=user.tenant_id, **self._scope()).one_or_none()
        plan = self.db.get(Plan, sub.plan_id) if sub else None
        now = self.clock()
        end = utc(sub.current_period_end) if sub and sub.current_period_end else None
        status = sub.status.value if sub else "not_contracted"
        if sub and sub.status == S.ACTIVE and end and end <= now:
            status = "expired" if sub.cancel_at_period_end else "past_due"
        pending = self.db.query(BillingCheckoutIntent).filter_by(tenant_id=user.tenant_id, provider="hotmart",
            provider_account_id=self.settings.account_id, environment=self.settings.environment, status=I.PENDING
            ).filter(BillingCheckoutIntent.expires_at > now).count() > 0
        return dict(enabled=self.settings.enabled, provider=sub.provider if sub else None, status=status,
            plan_name=plan.name if plan else None, period_end=end,
            cancel_at_period_end=bool(sub and sub.cancel_at_period_end), cancel_pending=bool(link and link.cancel_status == "pending"),
            can_cancel=bool(self.settings.enabled and link and link.cancel_status == "none" and sub and sub.status not in {S.CANCELED,S.EXPIRED}),
            can_checkout=bool(self.settings.enabled and not (link and link.cancel_status=="pending") and (sub is None or (sub.provider == "hotmart" and
                sub.status in {S.CANCELED,S.EXPIRED,S.INACTIVE}))),
            checkout_pending=pending, offers=self.offers(),
            events=[dict(type=e.event_type, received_at=utc(e.received_at), status=e.processing_status.value)
                for e in self.db.query(BillingEvent).filter_by(tenant_id=user.tenant_id,provider="hotmart",
                    provider_account_id=self.settings.account_id,environment=self.settings.environment).order_by(BillingEvent.id.desc()).limit(10)])

    def request_cancel(self, user):
        if not self.settings.enabled:
            raise BillingError("hotmart_disabled")
        link = self.db.query(HotmartSubscription).filter_by(tenant_id=user.tenant_id, **self._scope()).with_for_update().one_or_none()
        if link is None:
            raise BillingError("hotmart_subscription_not_found")
        if link.cancel_status != "none":
            return
        link.cancel_status, link.cancel_requested_by = "pending", user.id
        log_admin_action(self.db, tenant_id=user.tenant_id, user_id=user.id, action="billing.cancellation_requested",
            entity_type="subscription", entity_id=link.subscription_id, meta={"provider":"hotmart"})

    def process(self, event_id):
        event = self.db.query(BillingEvent).filter_by(id=event_id, provider="hotmart",provider_account_id=self.settings.account_id,
            environment=self.settings.environment).with_for_update().one()
        if event.processing_status == E.PROCESSED:
            return
        with billing_transaction(self.db):
            projection = validate_projection(json.loads(event.raw_payload)["projection"])
            self._apply(event, projection)
            event.processing_status = E.PROCESSED
            event.processed_at = self.clock()
            event.verification_status = V.VERIFIED
            event.verified_at = self.clock()
            event.error_code = None
            event.next_attempt_at = None
            event.attempt_count += 1
            self.db.flush()

    def _apply(self, event, p):
        kind, now = p["event"], self.clock()
        if kind not in EVENTS:
            raise BillingError("hotmart_event_requires_review")
        occurred = datetime.fromisoformat(p["occurred_at"])
        if occurred > now + timedelta(minutes=5):
            raise BillingError("hotmart_event_in_future")
        link = self.db.query(HotmartSubscription).filter_by(subscriber_code=p["subscriber_code"], **self._scope()).one_or_none()
        intent = None
        if link is not None and p["correlation"]:
            correlated = self.db.query(BillingCheckoutIntent).filter_by(public_token=p["correlation"],provider="hotmart",
                provider_account_id=self.settings.account_id,environment=self.settings.environment).one_or_none()
            if correlated is None or correlated.tenant_id != link.tenant_id:
                raise BillingError("hotmart_correlation_mismatch")
            if correlated.status == I.PENDING and kind in PAID:
                intent = correlated
            elif correlated.status != I.COMPLETED or correlated.external_subscription_id != p["subscriber_code"]:
                raise BillingError("hotmart_correlation_mismatch")
        if link is None:
            if kind not in PAID or not p["correlation"]:
                raise BillingError("hotmart_correlation_missing")
            intent = self.db.query(BillingCheckoutIntent).filter_by(public_token=p["correlation"], provider="hotmart",
                provider_account_id=self.settings.account_id, environment=self.settings.environment).one_or_none()
            if intent is None or intent.status != I.PENDING or utc(intent.expires_at) <= now:
                raise BillingError("hotmart_intent_unavailable")
            tenant_id = intent.tenant_id
        else:
            tenant_id = link.tenant_id
        # Stable lock shared by every delivery for this store, including initial binding.
        tenant = self.db.query(Tenant).filter_by(id=tenant_id, is_active=True).with_for_update().one_or_none()
        if tenant is None:
            raise BillingError("tenant_unavailable")
        link = self.db.query(HotmartSubscription).filter_by(tenant_id=tenant_id).populate_existing().with_for_update().one_or_none()
        mapping = self.mapping(p["product_id"], p["plan_id"]) if p["plan_id"] else None
        sub = self.db.query(Subscription).filter_by(tenant_id=tenant_id).populate_existing().with_for_update().one_or_none()
        actor = SubscriptionActor("provider", origin="hotmart", correlation_id=str(event.id))
        service = SubscriptionService(self.db, clock=self.clock)
        if intent:
            self.db.refresh(intent)
            if intent.status != I.PENDING or utc(intent.expires_at) <= now or mapping is None or mapping.plan_id != intent.plan_id:
                raise BillingError("hotmart_intent_plan_mismatch")
            if sub and (sub.provider != "hotmart" or (sub.current_period_end and utc(sub.current_period_end) > now and sub.status not in {S.CANCELED,S.EXPIRED,S.INACTIVE})):
                raise BillingError("existing_subscription_requires_review")
        elif (link is None or link.account_id != self.settings.account_id or link.environment != self.settings.environment
              or link.subscriber_code != p["subscriber_code"] or link.product_id != p["product_id"]
              or (p["plan_id"] and link.external_plan_id != p["plan_id"])):
            raise BillingError("hotmart_binding_mismatch")
        event.tenant_id = tenant_id
        event.subscription_id = sub.id if sub else None
        if link and link.last_event_at and occurred < utc(link.last_event_at):
            return
        if kind in PAID:
            start, end = datetime.fromisoformat(p["approved_at"]), datetime.fromisoformat(p["period_end"])
            if start > now or end <= now or end <= start or end - start > timedelta(days=40):
                raise BillingError("hotmart_invalid_monthly_paid_period")
            if mapping is None:
                raise BillingError("offer_not_mapped")
            if sub is None:
                sub = service.create_subscription(tenant_id, mapping.plan_id, provider="hotmart",
                    provider_subscription_id=p["subscriber_code"], actor=actor)
            if intent and (sub.status in {S.CANCELED,S.EXPIRED} or (sub.status == S.INACTIVE and sub.provider_subscription_id is None)):
                sub = service.restart_subscription(tenant_id, sub.id, plan_id=mapping.plan_id,
                    provider="hotmart", provider_subscription_id=p["subscriber_code"], current_period_start=start,
                    current_period_end=end, actor=actor)
            else:
                if sub.provider != "hotmart" or sub.provider_subscription_id != p["subscriber_code"] or sub.plan_id != mapping.plan_id:
                    raise BillingError("hotmart_binding_mismatch")
                current_end = utc(sub.current_period_end) if sub.current_period_end else None
                if sub.status == S.ACTIVE and current_end and end <= current_end:
                    if link and link.last_transaction != p["transaction"]:
                        raise BillingError("hotmart_non_advancing_payment")
                elif sub.cancel_at_period_end:
                    raise BillingError("hotmart_paid_after_cancel_requires_review")
                elif sub.status == S.ACTIVE:
                    service.renew_subscription(tenant_id,sub.id,current_period_start=start,current_period_end=end,actor=actor)
                elif sub.status in {S.INACTIVE,S.TRIALING,S.PAST_DUE}:
                    service.activate_subscription(tenant_id,sub.id,current_period_start=start,current_period_end=end,actor=actor)
                else:
                    raise BillingError("hotmart_terminal_subscription_requires_checkout")
            if intent:
                BillingCatalogService(self.db).complete_intent(tenant_id,intent.public_token,
                    external_checkout_id=p["transaction"],external_subscription_id=p["subscriber_code"],now=now)
            if link is None:
                link = HotmartSubscription(tenant_id=tenant_id,subscription_id=sub.id,**self._scope(),
                    subscriber_code=p["subscriber_code"],product_id=p["product_id"],external_plan_id=p["plan_id"])
                self.db.add(link)
            if intent:
                link.subscriber_code, link.product_id, link.external_plan_id = p["subscriber_code"],p["product_id"],p["plan_id"]
                link.cancel_status = "none"
                link.cancel_requested_by = None
            link.last_transaction = p["transaction"]
        elif kind == "SUBSCRIPTION_CANCELLATION":
            # Never extend access from a cancellation. Keep only the previously paid period.
            self.confirm_cancel(link, sub, actor)
        elif kind in REVOKED:
            if p["transaction"] != link.last_transaction:
                raise BillingError("hotmart_historical_refund_requires_review")
            if sub.status not in {S.CANCELED,S.EXPIRED}:
                service.cancel_subscription(tenant_id,sub.id,actor=actor)
            # Revocation of access is immediate; stopping future charges still needs provider confirmation.
            if link.cancel_status != "confirmed":
                link.cancel_status = "pending"
        elif kind == "PURCHASE_DELAYED":
            if sub.current_period_end and utc(sub.current_period_end) <= now and sub.status == S.ACTIVE:
                service.mark_past_due(tenant_id,sub.id,actor=actor)
        # PURCHASE_CANCELED is an unsuccessful charge, not subscription cancellation.
        link.last_event_at = occurred
        event.tenant_id, event.subscription_id = tenant_id, sub.id
        if intent:
            event.checkout_intent_id = intent.id

    def confirm_cancel(self, link, sub, actor):
        service = SubscriptionService(self.db, clock=self.clock)
        if sub.status not in {S.CANCELED,S.EXPIRED}:
            if sub.current_period_end and utc(sub.current_period_end) > self.clock() and sub.status in {S.ACTIVE,S.TRIALING}:
                if not sub.cancel_at_period_end:
                    service.schedule_cancellation(sub.tenant_id,sub.id,actor=actor)
            else:
                service.cancel_subscription(sub.tenant_id,sub.id,actor=actor)
        link.cancel_status = "confirmed"
