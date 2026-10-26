from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.models.tenant import Tenant
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.menu_item import MenuItem
from app.models.order import Order
from app.models.customer import Customer
from app.models.finance import CashMovement, OrderPayment
from app.models.native_payment import NativePaymentIntent
from app.routers import public_menu
from app.routers.store import router as store_router
from app.services import checkout_policy as policy

@pytest.fixture
def setup(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine); db=sessionmaker(bind=engine)()
    db.add_all([Tenant(id=1,slug='alpha',business_name='Alpha'),Tenant(id=2,slug='beta',business_name='Beta')]);db.flush()
    db.add(Plan(id=1,code='essential',name='Test plan',active=True));db.flush()
    db.add(Subscription(tenant_id=1,plan_id=1,status=SubscriptionStatus.ACTIVE,current_period_start=datetime.now(timezone.utc)-timedelta(days=1),current_period_end=datetime.now(timezone.utc)+timedelta(days=1)))
    db.add(MenuItem(id=1,tenant_id=1,name='Burger',price_cents=2500,active=True));db.commit()
    monkeypatch.setenv('CHECKOUT_POLICY_ENABLED','true');monkeypatch.setenv('CHECKOUT_POLICY_TENANT_IDS','1')
    monkeypatch.setattr(policy,'ENV_NORMALIZED','test')
    app=FastAPI();app.include_router(public_menu.router);app.include_router(store_router,prefix='/api/store')
    @app.middleware('http')
    async def scope(request,call_next):
        request.state.tenant=db.get(Tenant,1)
        return await call_next(request)
    app.dependency_overrides[get_db]=lambda:db
    yield SimpleNamespace(db=db,client=TestClient(app,raise_server_exceptions=False))
    db.close();engine.dispose()


def payload(method='pix'):
    return {'store_id':1,'customer_name':'Customer','customer_phone':'11912345678','delivery_type':'RETIRADA','order_type':'pickup','payment_method':method,'items':[{'item_id':1,'quantity':1}]}


def test_default_off_preserves_existing_methods_without_inferring_free(setup,monkeypatch):
    monkeypatch.delenv('CHECKOUT_POLICY_ENABLED')
    setup.db.query(Subscription).delete();setup.db.commit()
    result=setup.client.get('/public/checkout-policy')
    assert result.status_code==200
    assert [m['id'] for m in result.json()['methods']]==['pix','money','card']
    assert result.headers['cache-control']=='no-store'
    assert policy.resolve_checkout_policy(setup.db,1).enforced is False


def test_paid_active_methods_and_no_billing_details_in_public_response(setup):
    result=setup.client.get('/public/checkout-policy').json()
    assert {m['id'] for m in result['methods'] if m['available']}=={'pix','money','card'}
    assert all(not m['available'] for m in result['methods'] if m['id'].startswith('native_'))
    assert set(result)=={'methods','message'}


@pytest.mark.parametrize('method',['pix','manual_pix','money','cash','dinheiro','card','cartao','CARTÃO','external_card'])
@pytest.mark.parametrize('route',['/public/orders','/api/store/orders'])
def test_free_rejects_manual_methods_even_when_client_forges_plan(setup,method,route):
    s=setup;s.db.get(Plan,1).code='free';s.db.commit()
    data=payload(method);data.update(plan_code='pro',subscription_active=True,channel='marketplace',rate_bps=0)
    r=s.client.post(route,json=data)
    assert r.status_code==422,r.text
    assert s.db.query(Order).count()==0
    assert s.db.query(Customer).count()==0
    assert s.db.query(OrderPayment).count()==0
    assert s.db.query(CashMovement).count()==0


def test_free_exposes_only_unavailable_native_options_until_adapter_exists(setup):
    setup.db.get(Plan,1).code='free';setup.db.commit()
    result=setup.client.get('/public/checkout-policy').json()
    assert {m['id'] for m in result['methods']}=={'native_pix','native_card'}
    assert not any(m['available'] for m in result['methods'])
    assert result['message']


@pytest.mark.parametrize('enabled',[True,False])
@pytest.mark.parametrize('method',['native_pix','native_card','NATIVE_PIX'])
def test_native_never_creates_fake_paid_order_or_financial_records(setup,monkeypatch,enabled,method):
    monkeypatch.setenv('CHECKOUT_POLICY_ENABLED',str(enabled).lower())
    r=setup.client.post('/public/orders',json=payload(method))
    assert r.status_code==503,r.text
    for model in [Order,OrderPayment,CashMovement,NativePaymentIntent]: assert setup.db.query(model).count()==0


@pytest.mark.parametrize('status',[SubscriptionStatus.INACTIVE,SubscriptionStatus.TRIALING,SubscriptionStatus.PAST_DUE,SubscriptionStatus.CANCELED,SubscriptionStatus.EXPIRED])
def test_pilot_requires_active_commercial_assignment(setup,status):
    setup.db.query(Subscription).first().status=status;setup.db.commit()
    assert setup.client.get('/public/checkout-policy').json()['methods']==[]
    assert setup.client.post('/public/orders',json=payload()).status_code==409


@pytest.mark.parametrize('case',['missing','expired','future','no_end','plan_inactive','unknown_plan'])
def test_missing_or_invalid_commercial_state_fails_closed(setup,case):
    s=setup;sub=s.db.query(Subscription).first();plan=s.db.get(Plan,1)
    if case=='missing': s.db.delete(sub)
    elif case=='expired': sub.current_period_end=datetime.now(timezone.utc)-timedelta(seconds=1)
    elif case=='future': sub.current_period_start=datetime.now(timezone.utc)+timedelta(days=1)
    elif case=='no_end': sub.current_period_end=None
    elif case=='plan_inactive': plan.active=False
    else: plan.code='invented'
    s.db.commit()
    assert s.client.post('/public/orders',json=payload()).status_code==409
    assert s.db.query(Order).count()==0


@pytest.mark.parametrize('method,expected',[('pix','pix'),('money','cash'),('card','card')])
def test_paid_manual_creates_pending_collection_without_cash_movement(setup,method,expected):
    r=setup.client.post('/public/orders',json=payload(method))
    assert r.status_code==200,r.text
    payment=setup.db.query(OrderPayment).one()
    assert payment.status=='pending' and payment.paid_at is None and payment.method==expected
    assert payment.amount_cents==2500
    assert setup.db.query(CashMovement).count()==0
    assert setup.db.query(NativePaymentIntent).count()==0
    assert setup.db.query(Order).one().status=='pending'


def test_finance_failure_rolls_back_entire_pilot_order(setup,monkeypatch):
    def broken(*args,**kwargs): raise RuntimeError('Database finance failure')
    monkeypatch.setattr(public_menu,'create_order_payment',broken)
    r=setup.client.post('/public/orders',json=payload())
    assert r.status_code==500
    assert setup.db.query(Order).count()==0 and setup.db.query(Customer).count()==0


@pytest.mark.parametrize('route',['/public/orders','/api/store/orders'])
def test_cannot_select_another_store_via_body_store_id(setup,route):
    data=payload();data['store_id']=2
    assert setup.client.post(route,json=data).status_code==403
    assert setup.db.query(Order).count()==0


def test_client_cannot_bypass_with_unknown_or_missing_method(setup):
    for method in ['','unknown','Pix online']:
        assert setup.client.post('/public/orders',json=payload(method)).status_code==422


def test_allowlist_does_not_change_other_stores_and_production_pilot_is_blocked(setup,monkeypatch):
    assert policy.resolve_checkout_policy(setup.db,2).enforced is False
    monkeypatch.setattr(policy,'ENV_NORMALIZED','production')
    p=policy.resolve_checkout_policy(setup.db,1)
    assert p.reason=='pilot_environment_required' and not p.public_payload()['methods']
    assert setup.client.post('/public/orders',json=payload()).status_code==409


def test_invalid_configuration_fails_closed(setup,monkeypatch):
    for value in ['', 'not-an-id', '-1']:
        monkeypatch.setenv('CHECKOUT_POLICY_TENANT_IDS',value)
        assert setup.client.post('/public/orders',json=payload()).status_code==409
