"""Hourly authenticated reconciliation for bindings already proven by paid checkout."""
from datetime import timedelta
import hashlib
import json
from sqlalchemy import or_
from app.models.hotmart_subscription import HotmartSubscription
from app.models.subscription import Subscription, SubscriptionStatus as S
from app.services.billing_common import BillingError, utc
from app.services.billing_inbox import BillingInboxService
from app.services.hotmart_projection import millis


def reconcile(sessions,settings,api,now):
    count=errors=0
    # Reserve a due row before HTTP; multiple workers don't all poll the same store.
    for _ in range(25):
        with sessions() as db,db.begin():
            link=db.query(HotmartSubscription).join(Subscription,Subscription.id==HotmartSubscription.subscription_id).filter(
                HotmartSubscription.account_id==settings.account_id,HotmartSubscription.environment==settings.environment,
                Subscription.status.in_([S.ACTIVE,S.PAST_DUE]),
                or_(HotmartSubscription.reconcile_at.is_(None),HotmartSubscription.reconcile_at<=now)
                # Never-reviewed and most overdue bindings precede newer work.
                # Ordering by ID can starve later stores once due work exceeds
                # the cycle budget. Keep ID only as a deterministic tie-break.
                ).order_by(HotmartSubscription.reconcile_at.asc().nullsfirst(),
                           HotmartSubscription.id).with_for_update(skip_locked=True).first()
            if link is None:break
            link.reconcile_at=now+timedelta(hours=1)
            key=(link.id,link.subscriber_code,link.product_id,link.external_plan_id,link.last_transaction)
        link_id,code,product,plan,current_transaction=key
        try:
            proof=api.subscription(code,product)
            if str(proof.get("plan",{}).get("id"))!=plan or proof.get("trial") is True:
                raise BillingError("hotmart_subscription_mismatch")
            purchases=api.purchases(code)
            kind=transaction=start=end=None
            current=next((p for p in purchases if p.get("transaction")==current_transaction),None)
            if current and current.get("status") in {"REFUNDED","CHARGEBACK"}:
                kind="PURCHASE_"+current["status"]
                transaction=current_transaction
            elif proof.get("status") in {"CANCELLED_BY_CUSTOMER","CANCELLED_BY_SELLER","CANCELLED_BY_ADMIN"}:
                kind="SUBSCRIPTION_CANCELLATION"
            elif proof.get("status")=="ACTIVE":
                paid=[p for p in purchases if p.get("status") in {"APPROVED","COMPLETE"} and p.get("purchase_subscription") is True]
                if paid:
                    latest=max(paid,key=lambda p:millis(p.get("approved_date")))
                    if latest.get("transaction")!=current_transaction:
                        start=millis(latest.get("approved_date"))
                        end=millis(proof.get("date_next_charge"))
                        transaction=latest.get("transaction")
                        kind="PURCHASE_APPROVED"
            if kind is None:continue
            projection=dict(id="placeholder",event=kind,occurred_at=now.isoformat(),
                product_id=product,plan_id=plan,subscriber_code=code,transaction=transaction,
                purchase_status=kind.removeprefix("PURCHASE_") if kind!="SUBSCRIPTION_CANCELLATION" else None,
                approved_at=start.isoformat() if start else None,period_end=end.isoformat() if end else None,correlation=None)
            identity="reconcile_"+hashlib.sha256(json.dumps(projection,sort_keys=True).encode()).hexdigest()
            projection["id"]=identity
            with sessions() as db,db.begin():
                link=db.get(HotmartSubscription,link_id)
                if link.subscriber_code!=code:continue
                BillingInboxService(db).receive_event(provider="hotmart",environment=settings.environment,
                    provider_account_id=settings.account_id,provider_event_id=identity,event_type=kind,
                    payload=projection,schema_version=3,occurred_at=now,sanitized_projection=projection)
                count+=1
        except Exception:
            errors+=1
            with sessions() as db,db.begin():
                link=db.get(HotmartSubscription,link_id)
                if link:link.reconcile_at=now+timedelta(minutes=5)
    return count,errors
