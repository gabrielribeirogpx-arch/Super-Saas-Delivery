from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import hashlib
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
import pytest
from test_hotmart_billing import sessions,SETTINGS
from app.core.database import get_db
from app.models.onboarding_invite import OnboardingInvite
from app.models.subscription import Subscription,SubscriptionStatus as S
from app.models.tenant import Tenant
from app.services.onboarding_invites import issue_invite,consume_invite
import app.routers.onboarding as routes
import app.core.hotmart_config as config

BODY={'business_name':'Restaurante Convidado','admin_name':'Restaurante Owner','admin_email':'invited@example.com','admin_password':'test-password-123'}

@pytest.fixture
def client(sessions,monkeypatch):
    app=FastAPI();app.include_router(routes.router)
    def database():
        with sessions() as db:yield db
    app.dependency_overrides[get_db]=database
    monkeypatch.setattr(routes,'IS_PROD',True)
    monkeypatch.setattr(routes,'ONBOARDING_API_TOKEN','synthetic-operator-only-token')
    monkeypatch.setattr(config,'hotmart_settings',lambda:SETTINGS)
    with TestClient(app,raise_server_exceptions=False) as c:yield c


def issue(sessions):
    with sessions() as db,db.begin():return issue_invite(db)


def test_production_invite_creates_owner_and_inactive_subscription_without_admin_secret(client,sessions):
    token=issue(sessions)
    response=client.post('/api/onboarding/tenant',json=BODY,headers={'X-Onboarding-Invite':token})
    assert response.status_code==201,response.text
    assert response.json()['subscription_required']
    with sessions() as db:
        invite=db.query(OnboardingInvite).one()
        assert invite.consumed_at is not None and invite.token_hash!=token
        assert invite.token_hash==hashlib.sha256(token.encode()).hexdigest()
        sub=db.query(Subscription).filter_by(tenant_id=response.json()['tenant_id']).one()
        assert sub.status==S.INACTIVE and sub.provider=='hotmart'
    assert token not in response.text
    assert client.post('/api/onboarding/tenant',json=BODY,headers={'X-Onboarding-Invite':token}).status_code==401


def test_failed_signup_restores_invitation(client,sessions,monkeypatch):
    token=issue(sessions)
    def fail(*args):raise RuntimeError('synthetic setup failure')
    original=routes._seed_tenant_defaults
    monkeypatch.setattr(routes,'_seed_tenant_defaults',fail)
    assert client.post('/api/onboarding/tenant',json=BODY,headers={'X-Onboarding-Invite':token}).status_code==500
    with sessions() as db:
        assert db.query(OnboardingInvite).one().consumed_at is None
        assert db.query(Tenant).count()==2
    monkeypatch.setattr(routes,'_seed_tenant_defaults',original)
    assert client.post('/api/onboarding/tenant',json=BODY,headers={'X-Onboarding-Invite':token}).status_code==201


def test_invite_expiration_and_existing_production_gate(client,sessions):
    token=issue(sessions)
    with sessions() as db,db.begin():db.query(OnboardingInvite).one().expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
    assert client.post('/api/onboarding/tenant',json=BODY,headers={'X-Onboarding-Invite':token}).status_code==401
    assert client.post('/api/onboarding/tenant',json=BODY).status_code==401
    assert client.post('/api/onboarding/tenant',json=BODY,headers={'X-Onboarding-Invite':'invalid'}).status_code==401


def test_two_simultaneous_consumers_only_one_can_create_a_store(sessions):
    token=issue(sessions);barrier=Barrier(2)
    def consume():
        with sessions() as db,db.begin():
            barrier.wait(timeout=10)
            try:consume_invite(db,token);return True
            except HTTPException:return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(consume) for _ in range(2)]
        assert sorted(f.result(timeout=20) for f in futures)==[False,True]
