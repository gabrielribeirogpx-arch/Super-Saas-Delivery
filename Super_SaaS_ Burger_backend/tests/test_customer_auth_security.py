from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.models.customer import Customer
from app.models.customer_otp import CustomerOtp
from app.models.order import Order
from app.models.tenant import Tenant
from app.routers import customer_auth as auth
from app.routers.store import router as store_router
from app.services import auth as tokens

A, B = '11912345678', '11987654321'
original_provider = auth.provider

@pytest.fixture
def setup(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([Tenant(id=1, slug='alpha', business_name='Alpha'), Tenant(id=2, slug='beta', business_name='Beta')]); db.flush()
    for id, tenant, phone in [(1,1,A),(2,1,B),(3,2,A)]:
        db.add(Customer(id=id, tenant_id=tenant, phone=phone, phone_normalized=phone, is_active=True))
    db.flush()
    for id, tenant, customer in [(1,1,1),(2,1,2),(3,2,3)]:
        db.add(Order(id=id, tenant_id=tenant, customer_id=customer, cliente_nome='Customer', cliente_telefone=A, itens='Burger', valor_total=1000, total_cents=1000, status='RECEBIDO', tracking_token=f'opaque-order-{id}'))
    db.commit()
    for module in [auth,tokens]: monkeypatch.setattr(module,'JWT_SECRET_KEY','customer-security-tests-only-not-a-real-secret')
    monkeypatch.setattr(auth,'resolve_tenant',lambda request, session: session.get(Tenant,int(request.headers.get('x-test-tenant','1'))))
    delivered=[]
    class Capture:
        def send_code(self, **kwargs): delivered.append(kwargs['code'])
    monkeypatch.setattr(auth,'provider',lambda:Capture())
    app=FastAPI(); app.include_router(auth.router); app.include_router(store_router,prefix='/api/store')
    @app.middleware('http')
    async def scope(request, call_next):
        request.state.tenant=SimpleNamespace(id=int(request.headers.get('x-test-tenant','1')))
        return await call_next(request)
    app.dependency_overrides[get_db]=lambda:db
    yield SimpleNamespace(db=db,client=TestClient(app),delivered=delivered)
    db.close(); engine.dispose()

def request_code(s,phone=A):
    r=s.client.post('/api/public/customer-auth/request-code',json={'phone':phone,'accepted_terms':True})
    assert r.status_code==200,r.text
    assert 'test_code' not in r.json()
    return s.delivered[-1]

def verify(s,code,phone=A):
    return s.client.post('/api/public/customer-auth/verify-code',json={'phone':phone,'code':code})

def test_phone_proof_limits_history_and_reuses_legacy_guest(setup):
    s=setup; r=verify(s,request_code(s)); assert r.status_code==200,r.text
    assert 'access_token' not in r.json()
    assert 'HttpOnly' in r.headers['set-cookie'] and 'SameSite=lax' in r.headers['set-cookie'] and 'Domain=' not in r.headers['set-cookie']
    rows=s.client.get('/api/public/customer-auth/orders').json()
    assert [o['tracking_token'] for o in rows]==['opaque-order-1']
    assert s.db.query(Customer).count()==3
    assert s.client.get('/api/public/customer-auth/orders',headers={'x-test-tenant':'2'}).status_code==403
    assert s.client.get('/api/public/customer-auth/orders?customer_id=2&phone='+B).json()==rows

@pytest.mark.parametrize('path',['/api/public/customer-auth/orders','/api/public/customer-auth/me','/api/store/customer-orders?customer_id=1','/api/store/customer-profile?phone='+A,'/api/store/customer-addresses?phone='+A,'/api/store/customer-benefits?phone='+A])
def test_phone_or_id_without_session_never_grants_access(setup,path):
    assert setup.client.get(path).status_code==401

def test_unverified_legacy_token_and_bearer_rejected(setup):
    token=tokens.create_access_token('1',extra={'type':'customer','tenant_id':1,'customer_id':1})
    setup.client.cookies.set(auth.COOKIE_NAME,token)
    assert setup.client.get('/api/public/customer-auth/orders').status_code==401
    setup.client.cookies.clear()
    assert setup.client.get('/api/public/customer-auth/orders',headers={'Authorization':'Bearer '+token}).status_code==401

@pytest.mark.parametrize('claims',[{'customer_id':'1','tenant_id':1},{'customer_id':True,'tenant_id':1},{'customer_id':1,'tenant_id':'bad'}])
def test_malformed_claims_are_unauthorized_not_server_errors(setup,claims):
    token=tokens.create_access_token('1',extra={'type':'customer','phone_verified':True,**claims})
    setup.client.cookies.set(auth.COOKIE_NAME,token)
    assert setup.client.get('/api/public/customer-auth/me').status_code==401

def test_five_wrong_codes_lock_out_even_correct_code(setup):
    code=request_code(setup); wrong='000000' if code!='000000' else '111111'
    for _ in range(5): assert verify(setup,wrong).status_code==401
    assert verify(setup,code).status_code==401

def test_expired_used_and_other_tenant_code_rejected(setup):
    s=setup; code=request_code(s)
    assert s.client.post('/api/public/customer-auth/verify-code',headers={'x-test-tenant':'2'},json={'phone':A,'code':code}).status_code==401
    assert verify(s,code).status_code==200
    assert verify(s,code).status_code==401
    code=request_code(s,B)
    s.db.query(CustomerOtp).filter(CustomerOtp.phone_normalized==auth.normalize_phone(B)).first().expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);s.db.commit()
    assert verify(s,code,B).status_code==401

def test_cooldown_and_resend_invalidate_old_code(setup):
    s=setup; old=request_code(s)
    assert s.client.post('/api/public/customer-auth/request-code',json={'phone':A,'accepted_terms':True}).status_code==429
    s.db.query(CustomerOtp).first().created_at=datetime.now(timezone.utc)-timedelta(seconds=61);s.db.commit()
    new=request_code(s)
    if old!=new: assert verify(s,old).status_code==401
    assert verify(s,new).status_code==200

def test_owner_cannot_read_or_edit_another_customer_or_change_verified_phone(setup):
    s=setup; assert verify(s,request_code(s)).status_code==200
    assert s.client.get('/api/store/customer-profile',params={'phone':B}).status_code==403
    assert s.client.get('/api/store/customer-orders?customer_id=2').status_code==403
    assert s.client.patch('/api/store/customer-profile/2',json={'name':'Other'}).status_code==403
    assert s.client.patch('/api/store/customer-profile/1',json={'phone':B}).status_code==422

def test_disabled_customer_and_logout_have_no_history(setup):
    s=setup; assert verify(s,request_code(s)).status_code==200
    s.db.get(Customer,1).is_active=False;s.db.commit()
    assert s.client.get('/api/public/customer-auth/orders').status_code==401
    assert s.client.post('/api/public/customer-auth/logout').status_code==200
    assert s.client.get('/api/public/customer-auth/orders').status_code==401

def test_missing_provider_does_not_create_or_verify_codes(setup,monkeypatch):
    monkeypatch.setattr(auth,'provider',original_provider);monkeypatch.setattr(auth,'ENV_NORMALIZED','staging');monkeypatch.setenv('CUSTOMER_OTP_PROVIDER','test')
    assert setup.client.post('/api/public/customer-auth/request-code',json={'phone':A,'accepted_terms':True}).status_code==503
    assert setup.db.query(CustomerOtp).count()==0
    assert verify(setup,'123456').status_code==503

def test_send_failure_rolls_back_without_exposing_error(setup,monkeypatch):
    class Broken:
        def send_code(self,**kwargs): raise RuntimeError('secret-provider-error')
    monkeypatch.setattr(auth,'provider',lambda:Broken())
    r=setup.client.post('/api/public/customer-auth/request-code',json={'phone':A,'accepted_terms':True})
    assert r.status_code==503 and 'secret-provider-error' not in r.text
    assert setup.db.query(CustomerOtp).count()==0

def test_explicit_terms_and_no_code_in_logs(setup,capsys):
    assert setup.client.post('/api/public/customer-auth/request-code',json={'phone':A}).status_code==422
    code=request_code(setup);assert code not in capsys.readouterr().out


def test_another_verified_phone_sees_only_its_own_orders(setup):
    s=setup
    assert verify(s,request_code(s,B),B).status_code==200
    assert [row['tracking_token'] for row in s.client.get('/api/public/customer-auth/orders').json()]==['opaque-order-2']
    assert 'no-store' in s.client.get('/api/public/customer-auth/orders').headers['cache-control']


def test_legacy_phone_aliases_share_history_only_after_verification(setup):
    s=setup
    s.db.add(Customer(id=4,tenant_id=1,phone='+55'+A,phone_normalized='+55'+A,is_active=True));s.db.flush()
    s.db.add(Order(id=4,tenant_id=1,customer_id=4,cliente_nome='Same phone',cliente_telefone=A,itens='Burger',valor_total=1000,total_cents=1000,status='RECEBIDO',tracking_token='same-phone-other-row'));s.db.commit()
    assert s.client.get('/api/public/customer-auth/orders').status_code==401
    assert verify(s,request_code(s)).status_code==200
    assert {r['tracking_token'] for r in s.client.get('/api/public/customer-auth/orders').json()}=={'opaque-order-1','same-phone-other-row'}


def test_guest_cannot_overwrite_a_verified_profile(setup):
    from app.routers.public_menu import _get_or_create_customer
    s=setup
    assert verify(s,request_code(s)).status_code==200
    customer=s.db.get(Customer,1);customer.name='Verified';customer.email='owner@example.test';s.db.commit()
    found=_get_or_create_customer(s.db,1,'Unverified name','+55'+A,'other@example.test')
    assert found.id==1
    assert found.name=='Verified' and found.email=='owner@example.test'


def test_hourly_request_limit_cannot_be_reset_by_resending(setup):
    s=setup;now=datetime.now(timezone.utc)
    for i in range(10):
        s.db.add(CustomerOtp(tenant_id=1,phone_normalized=auth.normalize_phone(A),code_hash='old',expires_at=now,created_at=now-timedelta(minutes=2+i),used_at=now))
    s.db.commit()
    assert s.client.post('/api/public/customer-auth/request-code',json={'phone':A,'accepted_terms':True}).status_code==429
