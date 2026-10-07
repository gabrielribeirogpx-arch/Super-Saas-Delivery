"""Hourly reconciliation receipts originate from internal subscriptions only."""
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.billing_common import BillingError, utc
from app.services.billing_inbox import BillingInboxService
from app.services.kiwify_projection import external_id


def schedule_reconciliation(session_factory, settings, now):
    if not settings.enabled:
        return 0
    count, cursor = 0, 0
    bucket = utc(now).strftime("%Y%m%d%H")
    while True:
        with session_factory() as db:
            rows = db.query(Subscription.id, Subscription.tenant_id, Subscription.provider_subscription_id).filter(
                Subscription.id > cursor, Subscription.provider == "kiwify",
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE]))
            rows = rows.order_by(Subscription.id).limit(100).all()
        if not rows:
            return count
        for sub_id, tenant_id, external_sub in rows:
            cursor = sub_id
            try:
                external_id(external_sub)
            except BillingError:
                # No inferred IDs or scoped external calls for legacy bad bindings.
                continue
            with session_factory() as db, db.begin():
                projection = {"subscription_id": external_sub, "webhook_event_type": "subscription_reconciliation"}
                receipt = BillingInboxService(db).receive_event(provider="kiwify", environment=settings.environment,
                    provider_account_id=settings.account_id, provider_event_id=f"reconcile:{sub_id}:{bucket}",
                    event_type="subscription_reconciliation", payload=projection, schema_version=2, sanitized_projection=projection)
                # This is an INTERNAL candidate, not proof of external account scope.
                # Current API routes cannot validate it, so it goes to manual_review.
                BillingInboxService(db).link_event(receipt.event.id, tenant_id, subscription_id=sub_id, now=now)
                count += int(receipt.created)
