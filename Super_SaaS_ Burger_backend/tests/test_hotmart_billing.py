"""Contract, tenant isolation, atomic queue, paid periods and cancellation recovery."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import json
from urllib.parse import urlsplit,parse_qs
import httpx
import pytest
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from test_billing_phase2 import database
from app.core.database import get_db
from app.core.hotmart_config import HotmartSettings,HotmartOffer,hotmart_settings
from app.deps import require_admin_user
from app.models.admin_user import AdminUser
from app.models.admin_audit_log import AdminAuditLog
from app.models.billing_checkout_intent import BillingCheckoutIntent
from app.models.billing_event import BillingEvent,BillingEventStatus as E
from app.models.hotmart_subscription import HotmartSubscription
from app.models.subscription import Subscription,SubscriptionStatus as S
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.routers import hotmart_billing as routes
from app.services.hotmart_billing import HotmartBilling
from app.services.hotmart_worker import run_cycle
from app.services.hotmart_api import HotmartAPI,HotmartUnavailable
from app.services.billing_catalog import BillingCatalogService
from app.services.billing_common import BillingError
from app.services.subscriptions import SubscriptionService
from app.services.hotmart_access import require_hotmart_order_capacity,prepare_signup_subscription

NOW=datetime(2026,10,19,12,tzinfo=timezone.utc)
END=NOW+timedelta(days=30)
OFFER=HotmartOffer('essential','123','456','https://pay.hotmart.com/A123?off=offer1',9990)
SETTINGS=HotmartSettings(True,'sandbox','account-test','synthetic-hottok-123456','client','secret','basic',(OFFER,))
ROOT=routes.ROOT

@pytest.fixture
def sessions(tmp_path):
    engine=database(create_engine(f"sqlite:///{tmp_path/'hotmart.db'}",connect_args={'check_same_thread':False,'timeout':10}))
    factory=sessionmaker(bind=engine)
    with factory() as db,db.begin():
        for u in db.query(AdminUser):u.role='owner'
        plan=db.query(Plan).filter_by(code='essential').one()
        BillingCatalogService(db).create_mapping(provider='hotmart',environment='sandbox',provider_account_id='account-test',
            external_product_id='123',external_offer_id='456',plan_id=plan.id)
    yield factory
    engine.dispose()

@pytest.fixture
def client(sessions,monkeypatch):
    app=FastAPI();app.include_router(routes.router)
    def database_dep():
        with sessions() as db:yield db
    def actor():
        with sessions() as db:return db.get(AdminUser,1)
    app.dependency_overrides[get_db]=database_dep
    app.dependency_overrides[require_admin_user]=actor
    app.dependency_overrides[hotmart_settings]=lambda:SETTINGS
    original=HotmartBilling
    monkeypatch.setattr(routes,'HotmartBilling',lambda db,settings:original(db,settings,clock=lambda:NOW))
    with TestClient(app,headers={'X-Billing-Action':'1'}) as c:yield c


def start(client):
    response=client.post(ROOT+'/checkout',json={'plan_code':'essential'})
    assert response.status_code==200,response.text
    return parse_qs(urlsplit(response.json()['checkout_url']).query)['sck'][0]

def millis(date):return int(date.timestamp()*1000)

def payload(token=None,*,id='evt1',kind='PURCHASE_APPROVED',code='SUB1',transaction='HP1',start=NOW,end=END,occurred=NOW):
    data={'product':{'id':123},'subscription':{'status':'ACTIVE','plan':{'id':456},'subscriber':{'code':code}},
          'purchase':{'status':'APPROVED','transaction':transaction,'approved_date':millis(start),
                      'date_next_charge':millis(end),'origin':{'sck':token} if token else {}},
          'buyer':{'email':'PRIVATE_MARKER','document':'PRIVATE_MARKER'}}
    if kind=='SUBSCRIPTION_CANCELLATION':
        data['subscriber']={'code':code};data['date_next_charge']=millis(end)
    return {'id':id,'version':'2.0.0','creation_date':millis(occurred),'event':kind,'data':data}

def send(client,value):return client.post(routes.WEBHOOK_PATH,json=value,headers={'X-HOTMART-HOTTOK':SETTINGS.hottok})

class NoNetworkAPI:
    def subscription(self,*args):return {'plan':{'id':456},'status':'ACTIVE'}
    def cancel(self,code):pass

def cycle(sessions,now=NOW,api=None):return run_cycle(sessions,SETTINGS,clock=lambda:now,api=api or NoNetworkAPI())

def active(client,sessions):
    token=start(client)
    value=payload(token)
    assert send(client,value).status_code==202
    result=cycle(sessions);assert result['processed']==1,result
    return value


def test_checkout_never_activates_and_reuses_pending_intent(client,sessions):
    token=start(client)
    assert token==start(client) and len(token)>=43
    with sessions() as db:
        assert db.query(BillingCheckoutIntent).count()==1
        sub=db.query(Subscription).one();assert sub.status==S.INACTIVE and sub.provider=='hotmart'
        with pytest.raises(HTTPException):require_hotmart_order_capacity(db,1)
    response=client.get(ROOT);assert response.status_code==200
    assert response.json()['checkout_pending'] and response.json()['offers'][0]['price_cents']==9990
    assert token not in response.text and 'checkout_url' not in response.text


def test_paid_webhook_durable_then_worker_activates_and_deduplicates(client,sessions):
    token=start(client);value=payload(token)
    assert send(client,value).status_code==202
    with sessions() as db:assert db.query(Subscription).one().status==S.INACTIVE
    assert send(client,value).json()['duplicate']
    assert cycle(sessions)['processed']==1
    assert cycle(sessions)['processed']==0
    with sessions() as db:
        sub=db.query(Subscription).one();assert sub.status==S.ACTIVE
        assert sub.current_period_end.replace(tzinfo=timezone.utc)==END
        assert db.query(HotmartSubscription).one().last_transaction=='HP1'
        assert db.query(AdminAuditLog).filter_by(action='subscription.new_contract').count()==1
        assert 'PRIVATE_MARKER' not in db.query(BillingEvent).one().raw_payload
        require_hotmart_order_capacity(db,1)
    assert not client.get(ROOT).json()['can_checkout']
    assert client.post(ROOT+'/checkout',json={'plan_code':'essential'}).status_code==409

@pytest.mark.parametrize('header',[None,'wrong'])
def test_hottok_required_before_json_parsing(client,sessions,header):
    headers={'content-type':'application/json'}
    if header:headers['X-HOTMART-HOTTOK']=header
    assert client.post(routes.WEBHOOK_PATH,content='invalid',headers=headers).status_code==401
    with sessions() as db:assert db.query(BillingEvent).count()==0

@pytest.mark.parametrize('body',[b'{"x":1,"x":2}',b'{"x":NaN}',b'null',b'[]'])
def test_invalid_json_rejected(client,body):
    assert client.post(routes.WEBHOOK_PATH,content=body,headers={'X-HOTMART-HOTTOK':SETTINGS.hottok,'content-type':'application/json'}).status_code==422

def test_size_media_version_and_timestamp_contract(client):
    headers={'X-HOTMART-HOTTOK':SETTINGS.hottok}
    assert client.post(routes.WEBHOOK_PATH,content='{}',headers=headers).status_code==415
    assert client.post(routes.WEBHOOK_PATH,content='x'*65537,headers={**headers,'content-type':'application/json'}).status_code==413
    value=payload();value['version']='1.0.0';assert send(client,value).status_code==422
    value=payload();value['creation_date']=int(NOW.timestamp());assert send(client,value).status_code==422

@pytest.mark.parametrize('key',['approved_date','date_next_charge'])
def test_paid_dates_required_not_inferred(client,key):
    value=payload(start(client));del value['data']['purchase'][key]
    assert send(client,value).status_code==422


def test_identity_conflict_cannot_override_original(client,sessions):
    value=payload(start(client));assert send(client,value).status_code==202
    value['data']['product']['id']=999
    assert send(client,value).status_code==409
    assert cycle(sessions)['processed']==1

@pytest.mark.parametrize('mutation',['wrong_product','wrong_plan','missing_token','other_account','expired','canceled'])
def test_initial_correlation_and_mapping_fail_closed(client,sessions,mutation):
    value=payload(start(client))
    with sessions() as db,db.begin():
        intent=db.query(BillingCheckoutIntent).one()
        if mutation=='other_account':intent.provider_account_id='another-account'
        elif mutation=='expired':intent.expires_at=NOW-timedelta(seconds=1)
        elif mutation=='canceled':intent.status='canceled'
    if mutation=='wrong_product':value['data']['product']['id']=999
    if mutation=='wrong_plan':value['data']['subscription']['plan']['id']=999
    if mutation=='missing_token':value['data']['purchase']['origin']={}
    assert send(client,value).status_code==202
    assert cycle(sessions)['review']==1
    with sessions() as db:assert db.query(Subscription).one().status==S.INACTIVE


def test_renewal_without_original_token_extends_paid_period(client,sessions):
    active(client,sessions)
    next_now=END-timedelta(hours=1)
    value=payload(id='evt2',transaction='HP2',start=next_now,end=next_now+timedelta(days=30),occurred=next_now)
    assert send(client,value).status_code==202
    assert cycle(sessions,next_now)['processed']==1
    with sessions() as db:
        assert db.query(Subscription).one().current_period_end.replace(tzinfo=timezone.utc)>END
        assert db.query(AdminAuditLog).filter_by(action='subscription.renewed').count()==1


def test_out_of_order_payment_never_shrinks_period(client,sessions):
    first=active(client,sessions)
    later=END-timedelta(hours=1)
    assert send(client,payload(id='evt2',transaction='HP2',start=later,end=later+timedelta(days=30),occurred=later)).status_code==202
    cycle(sessions,later)
    first['id']='late-first';assert send(client,first).status_code==202
    assert cycle(sessions,later)['processed']==1
    with sessions() as db:assert db.query(HotmartSubscription).one().last_transaction=='HP2'


def test_cancellation_preserves_paid_period_and_expiration(client,sessions):
    active(client,sessions)
    value=payload(id='cancel',kind='SUBSCRIPTION_CANCELLATION',occurred=NOW+timedelta(seconds=1),end=END+timedelta(days=30))
    assert send(client,value).status_code==202
    assert cycle(sessions,NOW+timedelta(seconds=1))['processed']==1
    with sessions() as db:
        sub=db.query(Subscription).one();assert sub.status==S.ACTIVE and sub.cancel_at_period_end
        assert sub.current_period_end.replace(tzinfo=timezone.utc)==END
    cycle(sessions,END)
    with sessions() as db:
        assert db.query(Subscription).one().status==S.EXPIRED
        with pytest.raises(HTTPException):require_hotmart_order_capacity(db,1)

@pytest.mark.parametrize('kind',['PURCHASE_REFUNDED','PURCHASE_CHARGEBACK'])
def test_refund_or_chargeback_revokes_current_paid_cycle(client,sessions,kind):
    active(client,sessions)
    assert send(client,payload(id='refund',kind=kind,occurred=NOW+timedelta(seconds=1))).status_code==202
    assert cycle(sessions,NOW+timedelta(seconds=1))['processed']==1
    with sessions() as db:assert db.query(Subscription).one().status==S.CANCELED


def test_old_refund_does_not_revoke_new_cycle(client,sessions):
    active(client,sessions);later=END-timedelta(hours=1)
    send(client,payload(id='evt2',transaction='HP2',start=later,end=later+timedelta(days=30),occurred=later));cycle(sessions,later)
    send(client,payload(id='oldrefund',kind='PURCHASE_REFUNDED',occurred=later+timedelta(seconds=1)))
    assert cycle(sessions,later+timedelta(seconds=1))['review']==1
    with sessions() as db:assert db.query(Subscription).one().status==S.ACTIVE


def test_charge_canceled_does_not_cancel_paid_subscription(client,sessions):
    active(client,sessions)
    send(client,payload(id='cancelcharge',kind='PURCHASE_CANCELED',transaction='FAILED2',occurred=NOW+timedelta(seconds=1)))
    assert cycle(sessions,NOW+timedelta(seconds=1))['processed']==1
    with sessions() as db:assert db.query(Subscription).one().status==S.ACTIVE


def test_unpaid_expiry_blocks_orders_even_without_cron_then_paid_recovers(client,sessions):
    active(client,sessions)
    later=END+timedelta(hours=1)
    cycle(sessions,later)
    with sessions() as db:assert db.query(Subscription).one().status==S.PAST_DUE
    send(client,payload(id='recovery',transaction='HP2',start=later,end=later+timedelta(days=30),occurred=later))
    assert cycle(sessions,later)['processed']==1
    with sessions() as db:assert db.query(Subscription).one().status==S.ACTIVE


def test_cancel_request_is_durable_and_network_failure_never_claims_success(client,sessions):
    active(client,sessions)
    assert client.post(ROOT+'/cancel').json()['cancel_pending']
    assert client.post(ROOT+'/cancel').json()['cancel_pending']
    class Offline:
        def subscription(self,*args):raise RuntimeError('network')
    assert cycle(sessions,api=Offline())['errors']==1
    with sessions() as db:
        assert db.query(HotmartSubscription).one().cancel_status=='pending'
        assert not db.query(Subscription).one().cancel_at_period_end
        assert db.query(AdminAuditLog).filter_by(action='billing.cancellation_requested').count()==1
    class Online:
        calls=0
        def subscription(self,*args):return {'plan':{'id':456},'status':'ACTIVE'}
        def cancel(self,code):assert code=='SUB1';self.calls+=1
    online=Online();assert cycle(sessions,api=online)['canceled']==1 and online.calls==1
    assert cycle(sessions,api=online)['canceled']==0 and online.calls==1
    assert client.get(ROOT).json()['cancel_at_period_end']


def test_audit_failure_rolls_back_paid_binding_and_keeps_receipt(client,sessions,monkeypatch):
    import app.services.subscriptions as domain
    value=payload(start(client));send(client,value)
    monkeypatch.setattr(domain,'log_admin_action',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('audit')))
    assert cycle(sessions)['errors']==1
    with sessions() as db:
        assert db.query(Subscription).one().status==S.INACTIVE
        assert db.query(HotmartSubscription).count()==0
        assert db.query(BillingEvent).one().processing_status==E.PENDING
        assert db.query(BillingCheckoutIntent).one().status=='pending'

@pytest.mark.parametrize('role',['operator','cashier','delivery','viewer'])
def test_billing_financial_actions_rbac(client,sessions,role):
    with sessions() as db,db.begin():db.get(AdminUser,1).role=role
    assert client.get(ROOT).status_code==403
    assert client.post(ROOT+'/checkout',json={'plan_code':'essential'}).status_code==403
    assert client.post(ROOT+'/cancel').status_code==403


def test_tenant_substitution_and_csrf_headers(client,sessions):
    assert client.get(ROOT+'?tenant_id=2').status_code==403
    assert client.post(ROOT+'/checkout',json={'plan_code':'essential','tenant_id':2}).status_code==422
    client.headers.pop('X-Billing-Action')
    assert client.post(ROOT+'/checkout',json={'plan_code':'essential'}).status_code==422
    assert client.post(ROOT+'/cancel').status_code==422


def test_no_automatic_migration_of_existing_kiwify_contract(client,sessions):
    with sessions() as db,db.begin():
        plan=db.query(Plan).filter_by(code='essential').one()
        SubscriptionService(db,clock=lambda:NOW).create_subscription(1,plan.id,provider='kiwify')
    assert client.post(ROOT+'/checkout',json={'plan_code':'essential'}).status_code==409
    assert not client.get(ROOT).json()['can_checkout']

@pytest.mark.parametrize('url',['https://evil.test/pay','https://pay.hotmart.com.evil.test/X','http://pay.hotmart.com/X',
    'https://user:pass@pay.hotmart.com/X','https://pay.hotmart.com/X?sck=forged','https://pay.hotmart.com/X#fragment'])
def test_checkout_destination_allowlist(url):
    with pytest.raises(BillingError):replace(SETTINGS,offers=(replace(OFFER,checkout_url=url),)).validate()


def test_settings_disabled_default_and_invalid_configuration(monkeypatch):
    monkeypatch.delenv('HOTMART_BILLING_ENABLED',raising=False)
    assert not hotmart_settings().enabled
    SETTINGS.validate()
    for changes in [{'hottok':''},{'client_secret':''},{'environment':'unknown'},{'offers':()}]:
        with pytest.raises(BillingError):replace(SETTINGS,**changes).validate()


def test_api_oauth_cancel_bounded_and_fixed_hosts():
    requests=[]
    def handler(req):
        requests.append(req)
        if '/oauth/token' in str(req.url):return httpx.Response(200,json={'access_token':'mock','expires_in':3600})
        if req.method=='GET':return httpx.Response(200,json={'items':[{'subscriber_code':'SUB1','product':{'id':123},'plan':{'id':456},'status':'ACTIVE'}]})
        assert req.url.path.endswith('/SUB1/cancel') and json.loads(req.content)=={'send_mail':True}
        return httpx.Response(200,json={'subscriber_code':'SUB1','status':'INACTIVE'})
    api=HotmartAPI(SETTINGS,transport=httpx.MockTransport(handler))
    try:
        assert api.subscription('SUB1','123')['status']=='ACTIVE'
        api.cancel('SUB1')
        assert len(requests)==3
        assert requests[1].url.host=='sandbox.hotmart.com'
    finally:api.close()

@pytest.mark.parametrize('status',[401,403,429,500,302])
def test_provider_failure_is_sanitized(status):
    api=HotmartAPI(SETTINGS,transport=httpx.MockTransport(lambda _:httpx.Response(status,json={'secret':'PRIVATE_MARKER'})))
    try:
        with pytest.raises(HotmartUnavailable) as error:api.subscription('SUB1','123')
        assert 'PRIVATE_MARKER' not in str(error.value) and SETTINGS.client_secret not in str(error.value)
    finally:api.close()


def test_reconciliation_recovers_missed_paid_webhook_with_authenticated_history(client,sessions):
    active(client,sessions)
    later=END-timedelta(hours=1)
    class API:
        def subscription(self,*args):return {'plan':{'id':456},'status':'ACTIVE','trial':False,'date_next_charge':millis(later+timedelta(days=30))}
        def purchases(self,*args):return [{'transaction':'HP2','approved_date':millis(later),'status':'APPROVED','purchase_subscription':True}]
    assert run_cycle(sessions,SETTINGS,api=API(),clock=lambda:later,reconcile=True)['errors']==0
    assert cycle(sessions,later)['processed']==1
    with sessions() as db:
        assert db.query(HotmartSubscription).one().last_transaction=='HP2'
        assert db.query(Subscription).one().current_period_end.replace(tzinfo=timezone.utc)==later+timedelta(days=30)


def test_reconciliation_does_not_grant_access_from_next_charge_alone(client,sessions):
    active(client,sessions)
    class API:
        def subscription(self,*args):return {'plan':{'id':456},'status':'ACTIVE','date_next_charge':millis(END+timedelta(days=30))}
        def purchases(self,*args):return [{'transaction':'HP1','approved_date':millis(NOW),'status':'APPROVED','purchase_subscription':True}]
    assert run_cycle(sessions,SETTINGS,api=API(),clock=lambda:NOW+timedelta(minutes=20),reconcile=True)['errors']==0
    with sessions() as db:
        assert db.query(BillingEvent).count()==1
        assert db.query(Subscription).one().current_period_end.replace(tzinfo=timezone.utc)==END


def test_new_contract_after_paid_cancellation_preserves_audit(client,sessions):
    active(client,sessions)
    send(client,payload(id='refund',kind='PURCHASE_REFUNDED',occurred=NOW+timedelta(seconds=1)))
    cycle(sessions,NOW+timedelta(seconds=1))
    token=start(client)
    send(client,payload(token,id='new-contract',code='SUB2',transaction='HP2',occurred=NOW+timedelta(seconds=2)))
    assert cycle(sessions,NOW+timedelta(seconds=2))['processed']==1
    with sessions() as db:
        assert db.query(Subscription).count()==1 and db.query(Subscription).one().status==S.ACTIVE
        assert db.query(HotmartSubscription).one().subscriber_code=='SUB2'
        assert db.query(AdminAuditLog).filter_by(action='subscription.new_contract').count()==2


def test_enabled_signup_creates_inactive_contract_without_payment_or_trial(sessions,monkeypatch):
    import app.core.hotmart_config as config
    monkeypatch.setattr(config,'hotmart_settings',lambda:SETTINGS)
    with sessions() as db,db.begin():
        prepare_signup_subscription(db,2)
        sub=db.query(Subscription).filter_by(tenant_id=2).one()
        assert sub.status==S.INACTIVE and sub.provider=='hotmart' and sub.trial_end is None


def test_two_stores_get_distinct_intents_and_no_cross_store_access(client,sessions):
    first=start(client)
    with sessions() as db,db.begin():
        result=HotmartBilling(db,SETTINGS,clock=lambda:NOW).checkout(db.get(AdminUser,2),'essential')
    second=parse_qs(urlsplit(result['checkout_url']).query)['sck'][0]
    assert second!=first
    send(client,payload(first));cycle(sessions)
    with sessions() as db:
        assert db.query(Subscription).filter_by(tenant_id=1).one().status==S.ACTIVE
        assert db.query(Subscription).filter_by(tenant_id=2).one().status==S.INACTIVE


def test_existing_binding_does_not_accept_other_stores_checkout_token(client,sessions):
    active(client,sessions)
    with sessions() as db,db.begin():
        result=HotmartBilling(db,SETTINGS,clock=lambda:NOW).checkout(db.get(AdminUser,2),'essential')
    token=parse_qs(urlsplit(result['checkout_url']).query)['sck'][0]
    later=END-timedelta(hours=1)
    send(client,payload(token,id='wrong-store',transaction='HP2',start=later,end=later+timedelta(days=30),occurred=later))
    assert cycle(sessions,later)['review']==1
    with sessions() as db:
        assert db.query(HotmartSubscription).one().last_transaction=='HP1'
        assert db.query(Subscription).filter_by(tenant_id=2).one().status==S.INACTIVE

@pytest.mark.parametrize('paid_start,end',[(NOW+timedelta(days=1),END),(NOW,NOW),(NOW,NOW+timedelta(days=90))])
def test_invalid_paid_period_never_activates(client,sessions,paid_start,end):
    token=start(client)
    send(client,payload(token,start=paid_start,end=end))
    assert cycle(sessions)['review']==1
    with sessions() as db:assert db.query(Subscription).one().status==S.INACTIVE


def test_period_end_blocks_new_orders_even_when_cron_did_not_run(client,sessions,monkeypatch):
    from app.services import hotmart_access
    from app.services.entitlements import EntitlementService
    active(client,sessions)
    real=EntitlementService
    class AtExpiry(real):
        def evaluate(self,tenant,feature):return super().evaluate(tenant,feature,now=END)
    monkeypatch.setattr(hotmart_access,'EntitlementService',AtExpiry)
    with sessions() as db:
        assert db.query(Subscription).one().status==S.ACTIVE
        with pytest.raises(HTTPException):require_hotmart_order_capacity(db,1)


def test_cancel_pending_prevents_new_purchase_after_refund(client,sessions):
    active(client,sessions)
    class Offline:
        def subscription(self,*args):raise RuntimeError()
    send(client,payload(id='ref-pending',kind='PURCHASE_REFUNDED',occurred=NOW+timedelta(seconds=1)))
    cycle(sessions,NOW+timedelta(seconds=1),api=Offline())
    assert not client.get(ROOT).json()['can_checkout']
    assert client.post(ROOT+'/checkout',json={'plan_code':'essential'}).status_code==409


def test_outer_rollback_undoes_successful_event_application(client,sessions):
    value=payload(start(client));send(client,value)
    with sessions() as db:
        event_id=db.query(BillingEvent).one().id
        HotmartBilling(db,SETTINGS,clock=lambda:NOW).process(event_id)
        assert db.query(Subscription).one().status==S.ACTIVE
        db.rollback()
    with sessions() as db:
        assert db.query(Subscription).one().status==S.INACTIVE
        assert db.query(HotmartSubscription).count()==0
        assert db.query(BillingEvent).one().processing_status==E.PENDING


def test_ai_draft_creation_obeys_the_same_unpaid_access_gate(client,sessions):
    from app.ai.tools import ensure_open_order
    start(client)
    with sessions() as db:
        with pytest.raises(HTTPException):ensure_open_order(db,1,'fixture-phone')
