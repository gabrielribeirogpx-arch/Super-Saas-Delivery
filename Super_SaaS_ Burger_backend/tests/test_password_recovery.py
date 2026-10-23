import json
from urllib.parse import urlsplit, parse_qs
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_hotmart_billing import sessions
from app.core.database import get_db
from app.core import config
from app.models.admin_user import AdminUser
from app.models.admin_audit_log import AdminAuditLog
from app.routers import password_recovery as routes
from app.services import password_recovery as recovery
from app.services.passwords import verify_password,hash_password
from app.services.auth_service import AuthService
from app.services.admin_auth import create_admin_session
from starlette.requests import Request

@pytest.fixture
def client(sessions,monkeypatch):
    monkeypatch.setenv('RESEND_API_KEY','synthetic-private-key')
    monkeypatch.setenv('PASSWORD_RESET_BASE_DOMAIN','fomizero.com.br')
    monkeypatch.setattr(config,'ADMIN_SESSION_SECRET','synthetic-session-secret')
    monkeypatch.setattr('app.services.admin_auth.ADMIN_SESSION_SECRET','synthetic-session-secret')
    from app.core.rate_limiter import InMemoryRateLimiterService
    monkeypatch.setattr(routes,'_limiter',InMemoryRateLimiterService(limit=100))
    with sessions() as db,db.begin(): db.get(AdminUser,1).email='owner@example.com'
    app=FastAPI();app.include_router(routes.router)
    def database():
        with sessions() as db:yield db
    app.dependency_overrides[get_db]=database
    return TestClient(app)

@pytest.fixture
def mail(monkeypatch):
    sent=[]
    class Client:
        def __init__(self,**kw):assert kw=={'timeout':8,'follow_redirects':False}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,headers,json):
            assert url=='https://api.resend.com/emails'
            assert headers['Authorization']=='Bearer synthetic-private-key'
            sent.append(json);return httpx.Response(200,json={'id':'synthetic'})
    monkeypatch.setattr(recovery.httpx,'Client',Client)
    return sent


def request(client,sessions, email=None):
    with sessions() as db:
        user=db.get(AdminUser,1)
        from app.models.tenant import Tenant
        slug=db.get(Tenant,user.tenant_id).slug
        address=email or user.email
    return client.post('/api/admin/auth/forgot-password',json={'email':address,'tenant_slug':slug}),slug


def token(mail):
    link=mail[0]['text'].split('\n')[3]
    assert urlsplit(link).scheme=='https'
    assert not urlsplit(link).query
    return parse_qs(urlsplit(link).fragment)['token'][0]


def test_resend_scoped_link_single_use_and_password_update(client,sessions,mail):
    response,slug=request(client,sessions)
    assert response.status_code==202 and response.headers['cache-control']=='no-store'
    assert len(mail)==1 and mail[0]['from']=='Fomizero <acesso@fomizero.com.br>'
    secret=token(mail)
    assert secret not in response.text
    body={'token':secret,'password':'new-secure-password','tenant_slug':slug}
    assert client.post('/api/admin/auth/reset-password',json=body).status_code==200
    assert client.post('/api/admin/auth/reset-password',json=body).status_code==400
    with sessions() as db:
        user=db.get(AdminUser,1);assert user.credential_version==1
        assert verify_password(body['password'],user.password_hash)
        assert db.query(AdminAuditLog).filter_by(action='auth.password_reset').count()==1
        assert all(secret not in (a.meta_json or '') for a in db.query(AdminAuditLog))


def test_unknown_address_same_response_and_durable_cooldown(client,sessions,mail):
    first,_=request(client,sessions)
    assert request(client,sessions)[0].json()==first.json() and len(mail)==1
    assert request(client,sessions,'unknown@example.com')[0].json()==first.json() and len(mail)==1


def test_tampered_expired_wrong_store_and_changed_password_fail(client,sessions,mail,monkeypatch):
    _,slug=request(client,sessions);secret=token(mail)
    data={'token':secret,'password':'new-secure-password','tenant_slug':slug}
    assert client.post('/api/admin/auth/reset-password',json={**data,'tenant_slug':'another'}).status_code==400
    assert client.post('/api/admin/auth/reset-password',json={**data,'token':secret+'bad'}).status_code==400
    original=recovery.TTL;monkeypatch.setattr(recovery,'TTL',-1)
    assert client.post('/api/admin/auth/reset-password',json=data).status_code==400
    monkeypatch.setattr(recovery,'TTL',original)
    with sessions() as db,db.begin():db.get(AdminUser,1).password_hash=hash_password('changed-before-using-link')
    assert client.post('/api/admin/auth/reset-password',json=data).status_code==400


def test_provider_error_and_inactive_users_remain_generic(client,sessions,mail,monkeypatch):
    def fail(*a,**kw):raise httpx.TimeoutException('PRIVATE_PROVIDER_DETAILS')
    monkeypatch.setattr(recovery.httpx,'Client',fail)
    response,_=request(client,sessions)
    assert response.status_code==202 and 'PRIVATE_PROVIDER_DETAILS' not in response.text
    with sessions() as db:
        assert json.loads(db.query(AdminAuditLog).filter_by(action='auth.recovery_requested').one().meta_json)['delivery']=='failed'
    with sessions() as db,db.begin():db.get(AdminUser,1).active=False
    assert request(client,sessions)[0].json()==response.json() and len(mail)==0


def test_recovery_invalidates_previous_sessions_only_after_reset(client,sessions,mail):
    with sessions() as db:
        user=db.get(AdminUser,1)
        cookie=create_admin_session({'user_id':1,'tenant_id':user.tenant_id,'role':user.role})
        scope={'type':'http','headers':[(b'cookie',('admin_session='+cookie).encode())]}
        assert AuthService.authenticate_admin_session(Request(scope),db).id==1
    _,slug=request(client,sessions)
    assert client.post('/api/admin/auth/reset-password',json={'token':token(mail),'password':'new-password-123','tenant_slug':slug}).status_code==200
    with sessions() as db:
        from fastapi import HTTPException
        with pytest.raises(HTTPException):AuthService.authenticate_admin_session(Request(scope),db)
        fresh=create_admin_session({'user_id':1,'tenant_id':db.get(AdminUser,1).tenant_id,'role':'owner','credential_version':1})
        assert AuthService.authenticate_admin_session(Request({'type':'http','headers':[(b'cookie',('admin_session='+fresh).encode())]}),db).id==1


def test_config_and_limits_fail_safely(client,sessions,mail,monkeypatch):
    monkeypatch.delenv('RESEND_API_KEY')
    assert request(client,sessions)[0].status_code==503


def test_two_simultaneous_resets_only_one_wins(client,sessions,mail):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi import HTTPException
    _,slug=request(client,sessions);secret=token(mail);barrier=Barrier(2)
    def change(password):
        with sessions() as db:
            barrier.wait(timeout=10)
            try:recovery.reset_password(db,secret,password,slug);return True
            except HTTPException:return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(change,['first-password-123','second-password-123']))
    assert sorted(results)==[False,True]
    with sessions() as db:
        assert db.get(AdminUser,1).credential_version==1
        assert db.query(AdminAuditLog).filter_by(action='auth.password_reset').count()==1


def test_old_database_migration_preserves_password_and_can_roll_back(tmp_path,monkeypatch):
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    engine=sa.create_engine('sqlite:///'+str(tmp_path/'legacy.db'))
    with engine.begin() as c:
        c.exec_driver_sql('CREATE TABLE admin_users (id INTEGER PRIMARY KEY, password_hash VARCHAR NOT NULL)')
        c.exec_driver_sql("INSERT INTO admin_users VALUES (1,'preserved-test-hash')")
    root=Path(__file__).resolve().parents[1]
    cfg=Config(str(root/'alembic.ini'));cfg.set_main_option('script_location',str(root/'alembic'));cfg.set_main_option('sqlalchemy.url',str(engine.url))
    monkeypatch.setattr('logging.config.fileConfig',lambda *a,**k:None)
    command.stamp(cfg,'20261019_01_hotmart');command.upgrade(cfg,'20261023_01_admin_recovery')
    with engine.connect() as c:
        assert c.exec_driver_sql('SELECT password_hash,credential_version,recovery_sent_at FROM admin_users').one()==('preserved-test-hash',0,None)
    command.downgrade(cfg,'20261019_01_hotmart')
    assert {c['name'] for c in sa.inspect(engine).get_columns('admin_users')}=={'id','password_hash'}
    engine.dispose()
