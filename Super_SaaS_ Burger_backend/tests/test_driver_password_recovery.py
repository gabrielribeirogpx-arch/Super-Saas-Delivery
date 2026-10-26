from urllib.parse import urlsplit
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from app.models.admin_user import AdminUser
from app.models.tenant import Tenant
from app.routers import password_recovery as routes
from app.services import password_recovery as recovery
from app.services.passwords import verify_password
from app.services.auth import create_access_token, decode_access_token
from app.deps import _get_user_from_bearer_token
from test_password_recovery import client, mail, sessions, token

@pytest.fixture
def driver(client,sessions,monkeypatch):
    monkeypatch.setattr('app.services.auth.JWT_SECRET_KEY','synthetic-driver-jwt-key')
    client.app.include_router(routes.driver_router)
    with sessions() as db,db.begin():
        user=db.get(AdminUser,1);user.role='driver';user.email='driver@example.com'
        slug=db.get(Tenant,user.tenant_id).slug
        tid=user.tenant_id
    return {'tenant_slug':slug,'email':'driver@example.com'},tid


def test_driver_link_role_isolation_single_use_and_session_revocation(client,sessions,mail,driver,monkeypatch):
    payload,tid=driver
    old=create_access_token('1',extra={'tenant_id':tid,'delivery_user_id':1,'role':'driver'})
    from app.routers import delivery_ws
    monkeypatch.setattr(delivery_ws,'SessionLocal',sessions)
    assert delivery_ws._driver_session_valid(old)
    with sessions() as db:assert _get_user_from_bearer_token(old,db).id==1
    # Admin endpoint does not mail a driver; driver endpoint does.
    assert client.post('/api/admin/auth/forgot-password',json=payload).status_code==202
    assert not mail
    response=client.post('/api/driver/auth/forgot-password',json=payload)
    assert response.status_code==202 and response.headers['cache-control']=='no-store'
    secret=token(mail)
    assert '/driver/redefinir-senha#' in mail[0]['text']
    assert 'área do entregador' in mail[0]['html']
    assert client.post('/api/driver/auth/forgot-password',json=payload).json()==response.json()
    assert len(mail)==1
    data={'token':secret,'tenant_slug':payload['tenant_slug'],'password':'new-driver-password'}
    assert client.post('/api/admin/auth/reset-password',json=data).status_code==400
    assert client.post('/api/driver/auth/reset-password',json={**data,'tenant_slug':'other'}).status_code==400
    assert client.post('/api/driver/auth/reset-password',json=data).status_code==200
    assert len(mail)==2 and '/driver/login' in mail[1]['text']
    assert secret not in mail[1]['text']
    assert client.post('/api/driver/auth/reset-password',json=data).status_code==400
    assert len(mail)==2
    assert not delivery_ws._driver_session_valid(old)
    with sessions() as db:
        user=db.get(AdminUser,1)
        assert user.role=='driver' and user.tenant_id==tid and user.credential_version==1
        assert verify_password(data['password'],user.password_hash)
        with pytest.raises(HTTPException) as e:_get_user_from_bearer_token(old,db)
        assert e.value.status_code==401
        from types import SimpleNamespace
        from app.routers.driver_api import DriverLoginPayload,driver_login
        login=driver_login(DriverLoginPayload(email=payload['email'],password=data['password']),SimpleNamespace(state=SimpleNamespace(tenant=SimpleNamespace(id=tid))),db)
        fresh=login['token']
        assert decode_access_token(fresh)['credential_version']==1
        assert _get_user_from_bearer_token(fresh,db).id==1
    assert delivery_ws._driver_session_valid(fresh)


@pytest.mark.parametrize('role,active',[('owner',True),('operator',True),('driver',False),('delivery',False)])
def test_driver_recovery_unknown_inactive_and_other_roles_are_generic(client,sessions,mail,driver,role,active):
    payload,_=driver
    with sessions() as db,db.begin():
        user=db.get(AdminUser,1);user.role=role;user.active=active
    response=client.post('/api/driver/auth/forgot-password',json=payload)
    unknown=client.post('/api/driver/auth/forgot-password',json={**payload,'email':'unknown@example.com'})
    assert response.status_code==202 and response.json()==unknown.json()
    assert not mail


def test_delivery_role_expiry_tampering_and_admin_token_rejected(client,sessions,mail,driver,monkeypatch):
    payload,_=driver
    with sessions() as db,db.begin():db.get(AdminUser,1).role='delivery'
    client.post('/api/driver/auth/forgot-password',json=payload)
    secret=token(mail)
    data={'token':secret,'tenant_slug':payload['tenant_slug'],'password':'another-driver-password'}
    assert client.post('/api/driver/auth/reset-password',json={**data,'token':secret+'x'}).status_code==400
    with sessions() as db:
        user=db.get(AdminUser,1)
        forged_audience=recovery.serializer('admin').dumps(recovery.serializer('driver').loads(secret))
    assert client.post('/api/driver/auth/reset-password',json={**data,'token':forged_audience}).status_code==400
    monkeypatch.setattr(recovery,'TTL',-1)
    assert client.post('/api/driver/auth/reset-password',json=data).status_code==400
    assert len(mail)==1


def test_driver_reset_parallel_only_one_winner(client,sessions,mail,driver):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    payload,_=driver
    client.post('/api/driver/auth/forgot-password',json=payload);secret=token(mail);barrier=Barrier(2)
    def change(password):
        with sessions() as db:
            barrier.wait(timeout=10)
            try:recovery.reset_password(db,secret,password,payload['tenant_slug'],audience='driver');return True
            except HTTPException:return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(change,['driver-password-one','driver-password-two']))==[False,True]


@pytest.mark.parametrize('path',['/ws/driver','/ws/delivery','/ws/delivery/location'])
def test_open_driver_sockets_stop_after_credential_change(client,sessions,driver,monkeypatch,path):
    from app.routers import delivery_ws
    from starlette.websockets import WebSocketDisconnect
    payload,tid=driver
    with sessions() as db,db.begin():db.get(AdminUser,1).role='delivery'
    old=create_access_token('1',extra={'tenant_id':tid,'delivery_user_id':1,'role':'delivery'})
    monkeypatch.setattr(delivery_ws,'SessionLocal',sessions)
    monkeypatch.setattr(delivery_ws.TenantResolver,'resolve_tenant_id_from_request',lambda _:tid)
    monkeypatch.setattr(delivery_ws,'publish_delivery_status_event',lambda **kw:None)
    client.app.include_router(delivery_ws.router)
    with client.websocket_connect(path,headers={'authorization':'Bearer '+old}) as ws:
        with sessions() as db,db.begin():db.get(AdminUser,1).credential_version=1
        if path=='/ws/delivery':ws.send_text('ping')
        else:ws.send_json({'type':'driver_location_update','delivery_id':1,'lat':0,'lng':0})
        with pytest.raises(WebSocketDisconnect) as exc:ws.receive_json()
        assert exc.value.code==1008
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(path,headers={'authorization':'Bearer '+old}):pass
    assert exc.value.code==1008
