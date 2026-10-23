import json
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_hotmart_billing import sessions, SETTINGS
from test_onboarding_invites import BODY
from app.core.database import get_db
from app.core.rate_limiter import InMemoryRateLimiterService
from app.models.admin_audit_log import AdminAuditLog
from app.models.billing_offer_mapping import BillingOfferMapping
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.tenant import Tenant
import app.routers.onboarding as routes
import app.core.hotmart_config as billing
import app.services.public_signup as signup

@pytest.fixture
def client(sessions, monkeypatch):
    from app.routers.auth import router as legacy_auth
    app = FastAPI(); app.include_router(routes.router); app.include_router(legacy_auth)
    def database():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = database
    monkeypatch.setattr(routes, 'IS_PROD', True)
    monkeypatch.setattr(routes, 'ONBOARDING_API_TOKEN', 'operator-secret')
    monkeypatch.setattr(billing, 'hotmart_settings', lambda: SETTINGS)
    for key, value in dict(PUBLIC_SIGNUP_ENABLED='true', TURNSTILE_SITE_KEY='public-site-key', TURNSTILE_SECRET_KEY='private-secret',
        PUBLIC_SIGNUP_ORIGINS='https://fomizero.com.br', SALES_TERMS_URL='https://fomizero.com.br/termos',
        SALES_PRIVACY_URL='https://fomizero.com.br/privacidade', SALES_TERMS_VERSION='2026-10', SALES_SUPPORT_EMAIL='support@example.com').items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(signup, '_limiter', InMemoryRateLimiterService(limit=10, window_seconds=60))
    yield TestClient(app, raise_server_exceptions=False)


def mock_captcha(monkeypatch, **overrides):
    calls = []
    result = dict(success=True, hostname='fomizero.com.br', action='signup'); result.update(overrides)
    class CaptchaClient:
        def __init__(self, **kwargs): assert kwargs == dict(timeout=5, follow_redirects=False)
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, data):
            assert url == 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
            assert data == dict(secret='private-secret', response='one-use-token')
            calls.append(1)
            return httpx.Response(200, json=result)
    monkeypatch.setattr(signup.httpx, 'Client', CaptchaClient)
    return calls


def enroll(client, **values):
    return client.post('/api/onboarding/tenant', json={**BODY, 'captcha_token':'one-use-token',
        'accept_terms':True, 'terms_version':'2026-10', **values}, headers={'Origin':'https://fomizero.com.br'})


def test_public_enrollment_is_inactive_and_records_terms_without_credentials(client, sessions, monkeypatch):
    calls = mock_captcha(monkeypatch)
    response = enroll(client)
    assert response.status_code == 201, response.text
    assert response.json()['subscription_required'] and len(calls) == 1
    with sessions() as db:
        sub = db.query(Subscription).filter_by(tenant_id=response.json()['tenant_id']).one()
        assert sub.status == SubscriptionStatus.INACTIVE and sub.provider == 'hotmart'
        audit = db.query(AdminAuditLog).filter_by(action='onboarding.terms_accepted').one()
        assert json.loads(audit.meta_json)['version'] == '2026-10'
        assert 'one-use-token' not in audit.meta_json and 'private-secret' not in audit.meta_json
    assert 'private-secret' not in response.text

@pytest.mark.parametrize('values', [dict(captcha_token=None), dict(accept_terms=False), dict(terms_version='old'), dict(custom_domain='paid.example.com')])
def test_required_verification_and_terms(client, sessions, values):
    assert enroll(client, **values).status_code == 400
    with sessions() as db: assert db.query(Tenant).count() == 2

@pytest.mark.parametrize('result', [dict(success=False),dict(hostname='other.example'),dict(action='login')])
def test_captcha_bound_to_hostname_and_action(client, sessions, monkeypatch, result):
    mock_captcha(monkeypatch, **result)
    assert enroll(client).status_code == 400
    with sessions() as db: assert db.query(Tenant).count() == 2


def test_origin_and_missing_configuration_fail_closed(client, monkeypatch):
    assert client.post('/api/onboarding/tenant',json=BODY,headers={'Origin':'https://evil.example'}).status_code == 403
    monkeypatch.delenv('TURNSTILE_SECRET_KEY')
    assert enroll(client).status_code == 503
    response = client.get('/api/onboarding/sales-config')
    assert not response.json()['ready'] and response.json()['site_key'] == ''


def test_catalog_uses_valid_mappings_and_no_credentials(client, sessions):
    response = client.get('/api/onboarding/sales-config')
    assert response.status_code == 200 and response.json()['ready']
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['offers'][0]['price_cents'] == 9990
    for secret in ['private-secret','synthetic-hottok','account-test','checkout_url','client_secret']:
        assert secret not in response.text
    with sessions() as db, db.begin(): db.query(BillingOfferMapping).delete()
    assert not client.get('/api/onboarding/sales-config').json()['ready']
    assert enroll(client).status_code == 503


def test_rate_limit_and_provider_failure_do_not_create_store(client, sessions, monkeypatch):
    mock_captcha(monkeypatch)
    limiter = InMemoryRateLimiterService(limit=1)
    limiter.check(tenant_id='public-signup',endpoint='create')
    monkeypatch.setattr(signup, '_limiter', limiter)
    response = enroll(client)
    assert response.status_code == 429 and 'Retry-After' in response.headers
    with sessions() as db: assert db.query(Tenant).count() == 2


def test_disabled_public_signup_keeps_operator_gate(client, monkeypatch):
    monkeypatch.setenv('PUBLIC_SIGNUP_ENABLED','false')
    assert enroll(client).status_code == 401


def test_public_mode_does_not_allow_fake_operator_header_even_in_staging(client, monkeypatch):
    monkeypatch.setattr(routes, 'IS_PROD', False)
    response = client.post('/api/onboarding/tenant', json=BODY, headers={'X-Onboarding-Token':'fake'})
    assert response.status_code == 401


def test_captcha_provider_timeout_is_safe(client, sessions, monkeypatch):
    def timeout(*args, **kwargs): raise httpx.TimeoutException('private-request-details')
    monkeypatch.setattr(signup.httpx, 'Client', timeout)
    response = enroll(client)
    assert response.status_code == 503 and 'private-request-details' not in response.text
    with sessions() as db: assert db.query(Tenant).count() == 2


def test_legacy_registration_cannot_bypass_public_verification(client, sessions):
    response = client.post('/auth/register', json={'name':'Owner', 'email':'test@example.com',
        'password':'synthetic-password', 'business_name':'Robot store'})
    assert response.status_code == 410
    with sessions() as db: assert db.query(Tenant).count() == 2


def test_whitespace_store_name_is_rejected(client):
    assert enroll(client, business_name='   ').status_code == 422


def test_inconsistent_offer_mapping_is_not_advertised_or_sold(client, sessions):
    from app.models.plan import Plan
    from app.models.admin_user import AdminUser
    from app.services.hotmart_billing import HotmartBilling
    from app.services.billing_common import BillingError
    with sessions() as db, db.begin():
        other = db.query(Plan).filter(Plan.code != 'essential').first()
        db.query(BillingOfferMapping).one().plan_id = other.id
    assert not client.get('/api/onboarding/sales-config').json()['ready']
    with sessions() as db:
        with pytest.raises(BillingError, match='hotmart_offer_mapping_mismatch'):
            HotmartBilling(db, SETTINGS).checkout(db.get(AdminUser, 1), 'essential')
