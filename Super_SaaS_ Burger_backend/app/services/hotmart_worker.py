"""Restart-safe queue and cancellation worker. No network transaction locks."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import or_
from app.models.billing_event import BillingEvent, BillingEventStatus as E, BillingVerificationStatus as V
from app.models.hotmart_subscription import HotmartSubscription
from app.models.subscription import Subscription, SubscriptionStatus as S
from app.services.billing_common import BillingError, utc
from app.services.hotmart_api import HotmartAPI
from app.services.hotmart_billing import HotmartBilling
from app.services.subscriptions import SubscriptionActor, SubscriptionService


def run_cycle(sessions, settings, *, api=None, clock=None, reconcile=False):
    if not settings.enabled:
        return {"processed":0,"review":0,"canceled":0,"errors":0}
    clock = clock or (lambda: datetime.now(timezone.utc))
    now=clock()
    counts={"processed":0,"review":0,"canceled":0,"errors":0}
    with sessions() as db:
        ids=[i for i, in db.query(BillingEvent.id).filter_by(provider="hotmart",provider_account_id=settings.account_id,
            environment=settings.environment,processing_status=E.PENDING).filter(
                or_(BillingEvent.next_attempt_at.is_(None),BillingEvent.next_attempt_at<=now),
                BillingEvent.attempt_count<8).order_by(BillingEvent.id).limit(50)]
    for event_id in ids:
        with sessions() as db:
            try:
                HotmartBilling(db,settings,clock=clock).process(event_id)
                db.commit()
                counts["processed"]+=1
            except BillingError as exc:
                db.rollback()
                event=db.query(BillingEvent).filter_by(id=event_id).with_for_update().one()
                if event.processing_status!=E.PROCESSED:
                    event.attempt_count+=1
                    event.verification_status=V.MANUAL_REVIEW
                    event.error_code=str(exc)[:100]
                    event.next_attempt_at=now+timedelta(seconds=min(3600,30*2**min(event.attempt_count,7)))
                    db.commit()
                    counts["review"]+=1
            except Exception:
                db.rollback()
                counts["errors"]+=1
    owned=api is None
    api=api or HotmartAPI(settings)
    try:
        if reconcile:
            from app.services.hotmart_reconciliation import reconcile as reconcile_bindings
            _, errors = reconcile_bindings(sessions,settings,api,now)
            counts["errors"] += errors
        with sessions() as db:
            links=[(row.id,row.subscriber_code,row.product_id,row.external_plan_id) for row in db.query(HotmartSubscription).filter_by(
                account_id=settings.account_id,environment=settings.environment,cancel_status="pending").order_by(HotmartSubscription.id).limit(25)]
        for link_id,code,product,plan in links:
            try:
                proof=api.subscription(code,product)
                if str(proof.get("plan",{}).get("id"))!=plan:
                    raise BillingError("hotmart_subscription_mismatch")
                if proof.get("status") not in {"CANCELLED_BY_CUSTOMER","CANCELLED_BY_SELLER","CANCELLED_BY_ADMIN"}:
                    api.cancel(code)
                with sessions() as db,db.begin():
                    link=db.query(HotmartSubscription).filter_by(id=link_id,subscriber_code=code,
                        account_id=settings.account_id,environment=settings.environment).with_for_update().one_or_none()
                    if link and link.cancel_status=="pending":
                        sub=db.get(Subscription,link.subscription_id)
                        HotmartBilling(db,settings,clock=clock).confirm_cancel(link,sub,
                            SubscriptionActor("provider",origin="hotmart",correlation_id="cancellation"))
                        counts["canceled"]+=1
            except Exception:
                counts["errors"]+=1
        # Access is evaluated against paid dates, even if this cron is delayed.
        # Do not expire unpaid-but-renewable contracts: a later paid renewal can recover past_due.
        with sessions() as db,db.begin():
            rows=db.query(Subscription).join(HotmartSubscription,HotmartSubscription.subscription_id==Subscription.id).filter(
                HotmartSubscription.account_id==settings.account_id,HotmartSubscription.environment==settings.environment,
                Subscription.status==S.ACTIVE,Subscription.current_period_end<=now).with_for_update().all()
            for sub in rows:
                service=SubscriptionService(db,clock=clock)
                if sub.cancel_at_period_end:
                    service.expire_subscription(sub.tenant_id,sub.id)
                else:
                    service.mark_past_due(sub.tenant_id,sub.id)
    finally:
        if owned:
            api.close()
    return counts
