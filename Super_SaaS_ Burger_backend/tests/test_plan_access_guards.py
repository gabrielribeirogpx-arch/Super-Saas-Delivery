"""Actual API enforcement, quotas, recovery and legacy isolation."""
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
import pytest
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from test_billing_phase2 import database
from app.core.database import get_db
from app.deps import require_admin_user,get_request_tenant_id
from app.models.admin_user import AdminUser
from app.models.plan import Plan
from app.models.subscription import Subscription,SubscriptionStatus as S
from app.routers import admin_users,admin_delivery_users,inventory,reports,admin_marketing,admin_whatsapp,admin_tenant,hotmart_billing
from app.services.plan_access import feature_allowed,require_user_capacity,access_summary
from app.services.admin_bootstrap import upsert_admin_user
from app.services.tenant_resolver import TenantResolver

@pytest.fixture
def scope(tmp_path):
    engine=database(create_engine(f"sqlite:///{tmp_path/'guards.db'}",connect_args={'check_same_thread':False}))
    sessions=sessionmaker(bind=engine)
    with sessions() as db,db.begin():
        db.get(AdminUser,1).role='owner'
        for user in db.query(AdminUser):user.email=user.email.replace('example.test','example.com')
    app=FastAPI()
    for module in [admin_users,admin_delivery_users,inventory,reports,admin_marketing,admin_whatsapp,admin_tenant,hotmart_billing]:app.include_router(module.router)
    def database_dep():
        with sessions() as db:yield db
    def actor():
        with sessions() as db:return db.get(AdminUser,1)
    app.dependency_overrides[get_db]=database_dep
    app.dependency_overrides[require_admin_user]=actor
    app.dependency_overrides[get_request_tenant_id]=lambda:1
    with TestClient(app) as client:yield client,sessions
    engine.dispose()

def contract(sessions,plan='essential',status=S.ACTIVE,provider='hotmart',expired=False):
    now=datetime.now(timezone.utc)
    with sessions() as db,db.begin():
        plan_id=db.query(Plan).filter_by(code=plan).one().id
        row=db.query(Subscription).filter_by(tenant_id=1).one_or_none()
        if row is None:row=Subscription(tenant_id=1);db.add(row)
        row.plan_id=plan_id
        row.provider=provider;row.status=status
        row.current_period_start=now-timedelta(days=30 if expired else 1)
        row.current_period_end=now+timedelta(days=-1 if expired else 29)

def new_user(client,email='new@example.com',tenant=1):
    return client.post('/api/admin/users',json={'tenant_id':tenant,'email':email,'name':'New','role':'operator','password':'password123'})

@pytest.mark.parametrize('plan,feature,allowed',[
 ('essential','inventory',False),('essential','coupons',False),('essential','tracking',False),('essential','whatsapp',False),
 ('operation','inventory',True),('operation','coupons',True),('operation','tracking',True),('operation','whatsapp',True),
 ('operation','loyalty',False),('operation','advanced_reports',False),('operation','custom_domain',False),
 ('pro','loyalty',True),('pro','custom_domain',True),('pro','advanced_reports',True)])
def test_matrix(scope,plan,feature,allowed):
    _,sessions=scope;contract(sessions,plan)
    with sessions() as db:assert feature_allowed(db,1,feature) is allowed

@pytest.mark.parametrize('path',['/api/inventory/items','/api/reports/financial/summary','/api/admin/marketing/coupons',
 '/api/admin/marketing/loyalty','/api/admin/marketing/rewards','/api/admin/1/whatsapp/config','/api/admin/1/delivery-users/locations'])
def test_direct_api_read_is_blocked_for_essential(scope,path):
    client,sessions=scope;contract(sessions)
    response=client.get(path);assert response.status_code==403,response.text
    assert response.json()['detail']['code']=='subscription_required'

def test_marketing_write_and_cross_tenant_substitution(scope):
    client,sessions=scope;contract(sessions)
    assert client.post('/api/admin/marketing/coupons',json={'code':'TEST','discount_type':'fixed','discount_value':5}).status_code==403
    assert new_user(client,tenant=2).status_code==403
    r=client.get('/api/admin/billing/access?tenant_id=2',headers={'X-Tenant-ID':'2'})
    assert r.status_code==200 and r.json()['managed'] and not r.json()['features']['inventory']['allowed']

@pytest.mark.parametrize('plan,limit',[('essential',1),('operation',3),('pro',10)])
def test_team_capacity_includes_owner(scope,plan,limit):
    client,sessions=scope;contract(sessions,plan)
    with patch('app.routers.admin_users.hash_password',return_value='hash'):
        for i in range(limit-1):assert new_user(client,f'user{i}@example.com').status_code==201
        assert new_user(client,'overflow@example.com').status_code==403
    with sessions() as db:assert db.query(AdminUser).filter_by(tenant_id=1,active=True).count()==limit

@pytest.mark.parametrize('plan,limit',[('essential',1),('operation',5),('pro',15)])
def test_delivery_capacity(scope,plan,limit):
    client,sessions=scope;contract(sessions,plan)
    with patch('app.routers.admin_delivery_users.hash_password',return_value='hash'):
        for i in range(limit):
            r=client.post('/api/admin/1/delivery-users',json={'email':f'driver{i}@example.com','name':'Driver','password':'password123'})
            assert r.status_code==201,r.text
        assert client.post('/api/admin/1/delivery-users',json={'email':'extra@example.com','name':'Driver','password':'password123'}).status_code==403

def test_reactivation_role_change_and_reduction_after_expiry(scope):
    client,sessions=scope;contract(sessions)
    with sessions() as db,db.begin():
        off=AdminUser(tenant_id=1,email='off@example.com',name='Off',role='operator',active=False,password_hash='x')
        driver=AdminUser(tenant_id=1,email='driver@example.com',name='Driver',role='DELIVERY',active=True,password_hash='x')
        db.add_all([off,driver]);db.flush();off_id,driver_id=off.id,driver.id
    assert client.put(f'/api/admin/users/{off_id}',json={'active':True}).status_code==403
    assert client.put(f'/api/admin/users/{driver_id}',json={'role':'operator'}).status_code==403
    contract(sessions,expired=True)
    assert client.put(f'/api/admin/users/{driver_id}',json={'active':False}).status_code==200
    assert client.put('/api/admin/users/1',json={'name':'Owner updated'}).status_code==200
    assert client.get('/api/admin/users').status_code==200
    assert client.get('/api/admin/billing/access').json()['active'] is False

@pytest.mark.parametrize('status,expired',[(S.INACTIVE,False),(S.PAST_DUE,False),(S.CANCELED,False),(S.EXPIRED,False),(S.ACTIVE,True)])
def test_unpaid_pro_cannot_use_paid_features_or_add_seats(scope,status,expired):
    client,sessions=scope;contract(sessions,'pro',status=status,expired=expired)
    assert client.get('/api/admin/marketing/loyalty').status_code==403
    assert client.get('/api/inventory/items').status_code==403
    assert new_user(client).status_code==403
    assert client.get('/api/admin/billing/access').status_code==200

def test_bootstrap_cannot_bypass_capacity(scope):
    _,sessions=scope;contract(sessions)
    with sessions() as db:
        with pytest.raises(HTTPException):upsert_admin_user(db,tenant_id=1,email='bypass@example.com',name='X',role='admin',password='password123')
        db.rollback();assert db.query(AdminUser).filter_by(tenant_id=1).count()==1

def test_custom_domain_write_and_resolution(scope):
    client,sessions=scope;contract(sessions)
    assert client.patch('/api/admin/tenant',json={'slug':'legacy','custom_domain':'shop.example.com'}).status_code==403
    contract(sessions,'pro')
    assert client.patch('/api/admin/tenant',json={'slug':'legacy','custom_domain':'shop.example.com'}).status_code==200
    with sessions() as db:assert TenantResolver.find_active_tenant_by_custom_domain(db,'shop.example.com').id==1
    contract(sessions,'operation')
    with sessions() as db:assert TenantResolver.find_active_tenant_by_custom_domain(db,'shop.example.com') is None
    assert client.patch('/api/admin/tenant',json={'slug':'legacy','custom_domain':None}).status_code==200

@pytest.mark.parametrize('provider',[None,'kiwify'])
def test_legacy_is_unchanged(scope,provider):
    client,sessions=scope
    if provider:contract(sessions,provider=provider,status=S.INACTIVE)
    with sessions() as db:
        assert feature_allowed(db,1,'inventory') and not access_summary(db,1)['managed']
        require_user_capacity(db,1,role='operator')
    with patch('app.routers.admin_users.hash_password',return_value='hash'):assert new_user(client).status_code==201


def test_public_coupon_validation_cannot_bypass_plan(scope):
    from types import SimpleNamespace
    from app.routers.store import validate_coupon,ValidateCouponPayload
    _,sessions=scope;contract(sessions)
    request=SimpleNamespace(state=SimpleNamespace(tenant=SimpleNamespace(id=1)))
    with sessions() as db:
        with pytest.raises(HTTPException) as exc:
            validate_coupon(ValidateCouponPayload(code='SAVE',order_total=20),request,db)
        assert exc.value.status_code==403


def test_essential_order_status_has_no_gps_and_does_not_call_routing(scope):
    from app.models.order import Order
    from app.routers.public_tracking import _build_public_order_payload
    _,sessions=scope;contract(sessions)
    with sessions() as db,db.begin():
        order=Order(tenant_id=1,cliente_telefone='11999999999',itens='test',status='RECEBIDO',total_cents=2000,
                    destination_lat=-23.5,destination_lng=-46.6,driver_lat=-23.6,driver_lng=-46.7)
        db.add(order);db.flush()
        with patch('app.routers.public_tracking._build_live_progress_payload',side_effect=AssertionError('routing must not run')):
            value=_build_public_order_payload(db,order)
        assert value['status'] and value['total_cents']==2000
        for key in ['driver_lat','driver_lng','destination_lat','destination_lng','last_location','distance_meters']:
            assert value[key] is None


def test_essential_outbound_whatsapp_skips_provider(scope):
    from app.whatsapp.service import WhatsAppService
    _,sessions=scope;contract(sessions)
    with sessions() as db,patch.object(WhatsAppService,'_select_provider',side_effect=AssertionError('provider must not run')):
        assert WhatsAppService().send_text(db,tenant_id=1,to_phone='11999999999',text='test') is None


def test_paid_cancellation_keeps_features_until_end(scope):
    from app.services.hotmart_access import require_hotmart_order_capacity
    _,sessions=scope;contract(sessions,'operation')
    with sessions() as db,db.begin():
        db.query(Subscription).filter_by(tenant_id=1).one().cancel_at_period_end=True
    with sessions() as db:
        assert feature_allowed(db,1,'inventory')
        require_hotmart_order_capacity(db,1)


def test_socket_location_cannot_publish_without_entitlement(scope,monkeypatch):
    from app.routers import delivery_ws
    from starlette.websockets import WebSocketDisconnect
    client,sessions=scope;contract(sessions)
    # Production helper uses a fresh session for every message, including expiry.
    monkeypatch.setattr(delivery_ws,'SessionLocal',sessions)
    monkeypatch.setattr(delivery_ws,'decode_access_token',lambda _: {'role':'DELIVERY','tenant_id':1,'delivery_user_id':3})
    calls=[];monkeypatch.setattr(delivery_ws,'publish_delivery_location_event',lambda **v:calls.append(v))
    client.app.include_router(delivery_ws.router)
    with client.websocket_connect('/ws/delivery/location',headers={'authorization':'Bearer fixture'}) as ws:
        ws.send_json({'lat':-23.5,'lng':-46.6})
        with pytest.raises(WebSocketDisconnect) as exc:ws.receive_text()
        assert exc.value.code==1008
    assert not calls


def test_order_quota_does_not_disable_other_paid_features(scope):
    from app.models.order import Order
    _,sessions=scope;contract(sessions,'operation')
    with sessions() as db,db.begin():
        db.add_all([Order(tenant_id=1,cliente_telefone='11999999999',itens='test',status='RECEBIDO') for _ in range(1500)])
    with sessions() as db:
        summary=access_summary(db,1)
        assert summary['active']
        assert summary['features']['orders_monthly']['reason']=='limit_reached'
        assert summary['features']['inventory']['allowed']


def test_downgrade_keeps_existing_accounts_but_refuses_growth(scope):
    client,sessions=scope;contract(sessions,'operation')
    with patch('app.routers.admin_users.hash_password',return_value='hash'):
        assert new_user(client,'second@example.com').status_code==201
        assert new_user(client,'third@example.com').status_code==201
    contract(sessions,'essential')
    assert new_user(client,'fourth@example.com').status_code==403
    with sessions() as db:assert db.query(AdminUser).filter_by(tenant_id=1,active=True).count()==3
