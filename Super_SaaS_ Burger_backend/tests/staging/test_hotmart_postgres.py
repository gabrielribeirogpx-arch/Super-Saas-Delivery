"""Real PostgreSQL billing concurrency using owned disposable schemas."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from app.models.admin_user import AdminUser
from app.models.admin_audit_log import AdminAuditLog
from app.models.billing_checkout_intent import BillingCheckoutIntent
from app.models.billing_event import BillingEvent
from app.models.hotmart_subscription import HotmartSubscription
from app.models.plan import Plan
from app.models.subscription import Subscription,SubscriptionStatus as S
from app.services.billing_catalog import BillingCatalogService
from app.services.billing_inbox import BillingInboxService
from app.services.hotmart_billing import HotmartBilling
from app.services.hotmart_projection import project
from datetime import datetime,timedelta,timezone
from app.core.hotmart_config import HotmartSettings,HotmartOffer
NOW=datetime(2026,10,19,12,tzinfo=timezone.utc)
SETTINGS=HotmartSettings(True,'sandbox','account-test','synthetic-hottok-123456','client','secret','basic',
    (HotmartOffer('essential','123','456','https://pay.hotmart.com/A123',9990),))

def payload(token):
    return {'id':'evt1','version':'2.0.0','event':'PURCHASE_APPROVED','creation_date':int(NOW.timestamp()*1000),
        'data':{'product':{'id':123},'subscription':{'status':'ACTIVE','plan':{'id':456},'subscriber':{'code':'SUB1'}},
            'purchase':{'transaction':'HP1','status':'APPROVED','approved_date':int(NOW.timestamp()*1000),
                'date_next_charge':int((NOW+timedelta(days=30)).timestamp()*1000),'origin':{'sck':token}}}}


def setup(sessions):
    with sessions() as db,db.begin():
        plan=db.query(Plan).filter_by(code='essential').one()
        BillingCatalogService(db).create_mapping(provider='hotmart',environment='sandbox',provider_account_id=SETTINGS.account_id,
            external_product_id='123',external_offer_id='456',plan_id=plan.id)
        HotmartBilling(db,SETTINGS,clock=lambda:NOW).checkout(db.get(AdminUser,1),'essential')
        token=db.query(BillingCheckoutIntent).one().public_token
    data=payload(token);projection=project(data)
    with sessions() as db,db.begin():
        receipt=BillingInboxService(db).receive_event(provider='hotmart',environment='sandbox',provider_account_id=SETTINGS.account_id,
            provider_event_id='evt1',event_type='PURCHASE_APPROVED',payload=data,schema_version=3,
            sanitized_projection=projection,occurred_at=NOW)
        return receipt.event.id


def test_pg_concurrent_deliveries_activate_once(pg):
    _,_,sessions=pg
    event_id=setup(sessions)
    barrier=Barrier(2)
    def worker():
        with sessions() as db,db.begin():
            barrier.wait(timeout=15)
            HotmartBilling(db,SETTINGS,clock=lambda:NOW).process(event_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(worker) for _ in range(2)]
        for f in futures:f.result(timeout=30)
    with sessions() as db:
        assert db.query(Subscription).one().status==S.ACTIVE
        assert db.query(HotmartSubscription).count()==1
        assert db.query(AdminAuditLog).filter_by(action='subscription.new_contract').count()==1
        assert db.query(BillingEvent).one().processing_status=='processed'


def test_pg_concurrent_cancel_requests_create_one_audit(pg):
    _,_,sessions=pg
    event_id=setup(sessions)
    with sessions() as db,db.begin():HotmartBilling(db,SETTINGS,clock=lambda:NOW).process(event_id)
    barrier=Barrier(2)
    def worker():
        with sessions() as db,db.begin():
            user=db.get(AdminUser,1);barrier.wait(timeout=15)
            HotmartBilling(db,SETTINGS,clock=lambda:NOW).request_cancel(user)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(worker) for _ in range(2)]
        for f in futures:f.result(timeout=30)
    with sessions() as db:
        assert db.query(HotmartSubscription).one().cancel_status=='pending'
        assert db.query(AdminAuditLog).filter_by(action='billing.cancellation_requested').count()==1


def test_pg_signup_invite_is_consumed_once_under_concurrency(pg):
    from app.services.onboarding_invites import issue_invite,consume_invite
    from fastapi import HTTPException
    _,_,sessions=pg
    with sessions() as db,db.begin():token=issue_invite(db)
    barrier=Barrier(2)
    def consume():
        with sessions() as db,db.begin():
            barrier.wait(timeout=15)
            try:consume_invite(db,token);return True
            except HTTPException:return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(consume) for _ in range(2)]
        assert sorted(f.result(timeout=30) for f in futures)==[False,True]


@pytest.mark.parametrize('mode',['create','reactivate'])
def test_pg_concurrent_seats_cannot_exceed_plan(pg,mode):
    from app.services.plan_access import require_user_capacity
    from fastapi import HTTPException
    _,_,sessions=pg
    now=datetime.now(timezone.utc)
    with sessions() as db,db.begin():
        plan=db.query(Plan).filter_by(code='operation').one()
        db.add(Subscription(tenant_id=1,plan_id=plan.id,provider='hotmart',status=S.ACTIVE,
            current_period_start=now-timedelta(days=1),current_period_end=now+timedelta(days=29)))
        targets=[]
        if mode=='reactivate':
            for i in range(2):
                target=AdminUser(tenant_id=1,email=f'pending{i}@example.com',name='Pending',role='operator',active=False,password_hash='x')
                db.add(target);db.flush();targets.append(target.id)
    barrier=Barrier(2)
    def worker(i):
        with sessions() as db:
            target=db.get(AdminUser,targets[i]) if targets else None
            barrier.wait(timeout=15)
            try:
                require_user_capacity(db,1,role='operator',active=True,target=target)
                if target:target.active=True
                else:db.add(AdminUser(tenant_id=1,email=f'new{i}@example.com',name='New',role='operator',active=True,password_hash='x'))
                db.commit();return 'created'
            except HTTPException as exc:
                db.rollback();assert exc.status_code==403;return 'blocked'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(worker,range(2)))
    assert sorted(results)==['blocked','created']
    with sessions() as db:assert db.query(AdminUser).filter_by(tenant_id=1,active=True).count()==3
