import json
from datetime import datetime, timedelta, timezone
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
from app.models.admin_user import AdminUser
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


def test_public_enrollment_accepts_first_party_www_without_tenant_origins(client, sessions, monkeypatch):
    mock_captcha(monkeypatch, hostname='www.fomizero.com.br')
    response = client.post('/api/onboarding/tenant', json={**BODY, 'captcha_token':'one-use-token',
        'accept_terms':True, 'terms_version':'2026-10'}, headers={'Origin':'https://www.fomizero.com.br'})
    assert response.status_code == 201, response.text
    with sessions() as db:
        audit = db.query(AdminAuditLog).filter_by(action='onboarding.terms_accepted').one()
        assert json.loads(audit.meta_json)['origin'] == 'https://www.fomizero.com.br'


def test_second_pending_store_with_same_owner_email_is_blocked(client, sessions, monkeypatch):
    mock_captcha(monkeypatch)
    first = enroll(client, business_name='Restaurante Novo', admin_email='owner-pending@example.com')
    assert first.status_code == 201, first.text
    duplicate = enroll(client, business_name='Outra Loja', admin_email='OWNER-PENDING@example.com')
    assert duplicate.status_code == 409
    assert 'owner-pending@example.com' not in duplicate.text
    assert first.json()['slug'] not in duplicate.text
    with sessions() as db:
        assert db.query(Tenant).count() == 3

    # A display name does not identify a store; a different owner gets a unique URL.
    second_owner = enroll(client, business_name='Restaurante Novo', admin_email='other-owner@example.com')
    assert second_owner.status_code == 201, second_owner.text
    assert second_owner.json()['slug'] != first.json()['slug']


def test_paid_owner_can_open_another_store(client, sessions, monkeypatch):
    mock_captcha(monkeypatch)
    first = enroll(client, admin_email='multi-store@example.com')
    assert first.status_code == 201, first.text
    with sessions() as db, db.begin():
        sub = db.query(Subscription).filter_by(tenant_id=first.json()['tenant_id']).one()
        sub.status = SubscriptionStatus.ACTIVE
    second = enroll(client, business_name='Outra Operação', admin_email='multi-store@example.com')
    assert second.status_code == 201, second.text


def test_unverified_pending_email_reservation_expires_but_verified_one_does_not(client, sessions, monkeypatch):
    mock_captcha(monkeypatch)
    first = enroll(client, admin_email='reserved@example.com')
    assert first.status_code == 201
    with sessions() as db, db.begin():
        sub = db.query(Subscription).filter_by(tenant_id=first.json()['tenant_id']).one()
        sub.created_at = datetime.now(timezone.utc) - timedelta(minutes=31)
    second = enroll(client, business_name='Outra Loja', admin_email='reserved@example.com')
    assert second.status_code == 201, second.text
    with sessions() as db, db.begin():
        first_owner = db.query(AdminUser).filter_by(tenant_id=first.json()['tenant_id'], role='owner').one()
        first_owner.email_verified_at = datetime.now(timezone.utc)
    assert enroll(client, business_name='Terceira Loja', admin_email='reserved@example.com').status_code == 409


def test_email_verification_after_signup_does_not_interrupt_checkout(client, sessions, monkeypatch):
    from app.core import config, stripe_config
    from app.core.stripe_config import StripeOffer, StripeSettings
    from app.services.owner_email_verification import verification_link
    monkeypatch.setenv('RESEND_API_KEY', 'fake-resend-key')
    monkeypatch.setattr(config, 'ADMIN_SESSION_SECRET', 'integration-secret')
    monkeypatch.setattr(stripe_config, 'stripe_settings', lambda: StripeSettings(True, 'production',
        'acct_example', 'pk_live_example', 'rk_live_example', 'whsec_example_secret_123456',
        (StripeOffer('essential', 'price_example', 9990),)))
    monkeypatch.setattr('app.services.transactional_emails.deliver_account_message', lambda *args: None)
    def stripe_request(settings, method, path, **kwargs):
        if method == 'GET':
            return dict(active=True, currency='brl', unit_amount=9990,
                recurring=dict(interval='month', interval_count=1))
        if path == 'customers': return dict(id='cus_example')
        return dict(id='sub_example', status='incomplete',
            latest_invoice=dict(confirmation_secret=dict(client_secret='pi_example_secret')))
    monkeypatch.setattr('app.services.stripe_billing.stripe_request', stripe_request)
    mock_captcha(monkeypatch)
    response = enroll(client, plan_code='essential', admin_email='verify@example.com')
    assert response.status_code == 201, response.text
    assert response.json()['stripe_checkout']['client_secret'] == 'pi_example_secret'
    with sessions() as db:
        owner = db.query(AdminUser).filter_by(tenant_id=response.json()['tenant_id'], role='owner').one()
        assert owner.email_verification_required and owner.email_verified_at is None
        token = verification_link(owner).split('#token=', 1)[1]
    assert client.post('/api/onboarding/verify-email', json={'token': token + 'tampered'}).status_code == 400
    verified = client.post('/api/onboarding/verify-email', json={'token': token})
    assert verified.status_code == 200 and verified.json()['slug'] == response.json()['slug']
    assert client.post('/api/onboarding/verify-email', json={'token': token}).status_code == 200
    with sessions() as db:
        assert db.query(AdminUser).filter_by(tenant_id=response.json()['tenant_id'], role='owner').one().email_verified_at


def test_owner_can_correct_unverified_email_and_old_link_stops_working(client, sessions, monkeypatch):
    from app.core import config
    from app.services.owner_email_verification import change_unverified_email, reserve_resend, verification_link
    monkeypatch.setenv('RESEND_API_KEY', 'fake-resend-key')
    monkeypatch.setattr(config, 'ADMIN_SESSION_SECRET', 'integration-secret')
    monkeypatch.setattr('app.services.transactional_emails.deliver_account_message', lambda *args: None)
    mock_captcha(monkeypatch)
    response = enroll(client, admin_email='mistyped@example.com')
    assert response.status_code == 201, response.text
    with sessions() as db:
        owner = db.query(AdminUser).filter_by(tenant_id=response.json()['tenant_id'], role='owner').one()
        old_token = verification_link(owner).split('#token=', 1)[1]
        assert reserve_resend(db, owner) is None  # the signup email just reserved its send slot
        change_unverified_email(db, owner, 'corrected@example.com', BODY['admin_password'])
        assert db.get(AdminUser, owner.id).email == 'corrected@example.com'
    assert client.post('/api/onboarding/verify-email', json={'token': old_token}).status_code == 400

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


def test_stripe_signup_opens_embedded_checkout_after_store_commit(client, sessions, monkeypatch):
    from app.core import stripe_config
    from app.core.stripe_config import StripeOffer, StripeSettings
    from app.models.plan import Plan
    settings = StripeSettings(True, 'production', 'acct_example', 'pk_live_example', 'rk_live_example',
        'whsec_example_secret_123456', (StripeOffer('operation', 'price_example', 17990),))
    monkeypatch.setattr(stripe_config, 'stripe_settings', lambda: settings)
    mock_captcha(monkeypatch)

    def stripe_request(settings, method, path, **kwargs):
        with sessions() as other_db:
            assert other_db.query(Tenant).filter_by(business_name='Test Stripe Fomizero').one_or_none() is not None
        if method == 'GET' and path == 'prices/price_example':
            return dict(active=True, currency='brl', unit_amount=17990,
                recurring=dict(interval='month', interval_count=1))
        if method == 'POST' and path == 'customers':
            return dict(id='cus_example')
        assert method == 'POST' and path == 'subscriptions'
        return dict(id='sub_example', status='incomplete',
            latest_invoice=dict(confirmation_secret=dict(client_secret='pi_example_secret')))

    monkeypatch.setattr('app.services.stripe_billing.stripe_request', stripe_request)
    response = enroll(client, plan_code='operation', business_name='Test Stripe Fomizero')
    assert response.status_code == 201, response.text
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['checkout_url'] is None
    assert response.json()['stripe_checkout']['client_secret'] == 'pi_example_secret'
    with sessions() as db:
        sub = db.query(Subscription).filter_by(tenant_id=response.json()['tenant_id']).one()
        assert sub.provider == 'stripe' and sub.status == SubscriptionStatus.INACTIVE
        assert sub.provider_customer_id == 'cus_example' and sub.provider_subscription_id == 'sub_example'
        assert db.get(Plan, sub.plan_id).code == 'operation'


def test_stripe_signup_keeps_store_when_checkout_is_temporarily_unavailable(client, sessions, monkeypatch):
    from app.core import stripe_config
    from app.core.stripe_config import StripeOffer, StripeSettings
    from app.services.billing_common import BillingError
    from app.services.stripe_billing import StripeBilling
    settings = StripeSettings(True, 'production', 'acct_example', 'pk_live_example', 'rk_live_example',
        'whsec_example_secret_123456', (StripeOffer('essential', 'price_example', 9990),))
    monkeypatch.setattr(stripe_config, 'stripe_settings', lambda: settings)
    monkeypatch.setattr(StripeBilling, 'checkout', lambda *args: (_ for _ in ()).throw(BillingError('stripe_unavailable')))
    mock_captcha(monkeypatch)
    response = enroll(client, plan_code='essential')
    assert response.status_code == 201, response.text
    assert response.json()['stripe_checkout'] is None
    with sessions() as db:
        sub = db.query(Subscription).filter_by(tenant_id=response.json()['tenant_id']).one()
        assert sub.provider == 'stripe' and sub.status == SubscriptionStatus.INACTIVE


def test_invalid_stripe_configuration_does_not_advertise_hotmart(client, monkeypatch):
    monkeypatch.setenv('STRIPE_BILLING_ENABLED', 'true')
    # Missing Stripe credentials must fail closed without directing customers to Hotmart.
    response = client.get('/api/onboarding/sales-config')
    assert response.status_code == 200
    assert response.json()['provider'] == 'stripe'
    assert response.json()['ready'] is False
    assert response.json()['offers'] == []


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


def test_selected_plan_creates_checkout_atomically_without_login(client, sessions, monkeypatch):
    from urllib.parse import parse_qs, urlsplit
    from app.models.billing_checkout_intent import BillingCheckoutIntent, BillingIntentStatus
    from app.models.admin_user import AdminUser
    mock_captcha(monkeypatch)
    response = enroll(client, plan_code='essential', tenant_id=1)
    assert response.status_code == 201, response.text
    assert response.headers['cache-control'] == 'no-store'
    result = response.json()
    assert result['tenant_id'] != 1
    token = parse_qs(urlsplit(result['checkout_url']).query)['sck'][0]
    assert len(token) == 43
    assert 'admin_session' not in response.cookies
    with sessions() as db:
        intent = db.query(BillingCheckoutIntent).filter_by(public_token=token).one()
        owner = db.query(AdminUser).filter_by(tenant_id=result['tenant_id']).one()
        assert intent.tenant_id == owner.tenant_id == result['tenant_id']
        assert intent.status == BillingIntentStatus.PENDING
        sub = db.query(Subscription).filter_by(tenant_id=result['tenant_id']).one()
        assert sub.status == SubscriptionStatus.INACTIVE


def test_invalid_selected_plan_creates_no_store(client, sessions, monkeypatch):
    mock_captcha(monkeypatch)
    assert enroll(client, plan_code='not_available').status_code == 400
    with sessions() as db: assert db.query(Tenant).count() == 2


def test_checkout_setup_failure_rolls_back_store_owner_and_terms(client, sessions, monkeypatch):
    from app.services.hotmart_billing import HotmartBilling
    from app.services.billing_common import BillingError
    from app.models.admin_user import AdminUser
    from app.models.billing_checkout_intent import BillingCheckoutIntent
    mock_captcha(monkeypatch)
    def fail(*args): raise BillingError('synthetic-private-error')
    monkeypatch.setattr(HotmartBilling, 'checkout', fail)
    response = enroll(client, plan_code='essential')
    assert response.status_code == 503 and 'synthetic-private-error' not in response.text
    with sessions() as db:
        assert db.query(Tenant).count() == 2
        assert db.query(AdminUser).filter_by(email=BODY['admin_email']).count() == 0
        assert db.query(AdminAuditLog).filter_by(action='onboarding.terms_accepted').count() == 0
        assert db.query(BillingCheckoutIntent).count() == 0


def test_native_signup_proves_email_once_without_browser_captcha(client, sessions, monkeypatch):
    from app.core import config
    from app.services import native_signup

    monkeypatch.delenv('TURNSTILE_SECRET_KEY')
    monkeypatch.setenv('RESEND_API_KEY', 'fake-resend-key')
    monkeypatch.setattr(config, 'ADMIN_SESSION_SECRET', 'integration-secret')
    monkeypatch.setattr(native_signup, '_send_limit', InMemoryRateLimiterService(limit=10, window_seconds=60))
    monkeypatch.setattr(native_signup, '_address_limit', InMemoryRateLimiterService(limit=3, window_seconds=900))
    monkeypatch.setattr('app.services.transactional_emails.deliver_account_message', lambda *args: None)
    messages = []

    def send(address, message):
        messages.append((address, message.text))
        return 'accepted'

    monkeypatch.setattr(native_signup, 'send_email', send)
    sales = client.get('/api/onboarding/sales-config').json()
    assert sales['native_ready'] and not sales['ready']
    assert client.post('/api/onboarding/native/email-code', json={'email': BODY['admin_email']}).status_code == 204
    assert messages[0][0] == BODY['admin_email']
    code = messages[0][1].split()[1]
    headers = {'X-Native-Signup-Code': code}
    payload = {**BODY, 'accept_terms': True, 'terms_version': '2026-10'}
    assert client.post('/api/onboarding/tenant', headers=headers,
        json={**payload, 'admin_email': 'different@example.com'}).status_code == 401
    assert client.post('/api/onboarding/tenant', headers=headers,
        json={**payload, 'terms_version': 'outdated'}).status_code == 400
    response = client.post('/api/onboarding/tenant', headers=headers, json=payload)
    assert response.status_code == 201, response.text
    assert client.post('/api/onboarding/tenant', headers=headers, json=payload).status_code == 401
    with sessions() as db:
        owner = db.query(AdminUser).filter_by(tenant_id=response.json()['tenant_id']).one()
        assert owner.email_verified_at is not None
        audit = db.query(AdminAuditLog).filter_by(action='onboarding.terms_accepted').one()
        assert json.loads(audit.meta_json)['origin'] == 'gestao_android'
        assert code not in audit.meta_json
