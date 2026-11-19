import base64
import json
from datetime import datetime, timedelta, timezone
from html import escape
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_hotmart_billing import sessions
from test_public_signup import client, mock_captcha, enroll
from app.services import transactional_emails as mail
from app.core.database import get_db
from app.deps import get_current_admin_user
from app.models.admin_audit_log import AdminAuditLog
from app.models.admin_user import AdminUser


def test_templates_escape_personal_fields_and_contain_matching_text_and_html(monkeypatch):
    monkeypatch.setenv('PASSWORD_RESET_BASE_DOMAIN','staging.fomizero.com.br')
    monkeypatch.setenv('SALES_SUPPORT_EMAIL','suporte@example.com')
    name='<img src=x onerror=alert(1)>'
    store='Loja <script>alert(1)</script>'
    reset='https://burger.staging.fomizero.com.br/redefinir-senha#token=synthetic-token'
    messages=[mail.recovery_message(name,store,reset),mail.welcome_message(name,store,'burger'),mail.password_changed_message(name,store,'burger')]
    for message in messages:
        assert '<script>' not in message.html and '<img src=x' not in message.html
        assert escape(store) in message.html and store in message.text
        assert 'cid:fomizero-logo' in message.html and 'lang="pt-BR"' in message.html
        assert 'suporte@example.com' in message.html and 'suporte@example.com' in message.text
        assert 'href="javascript:' not in message.html
    assert '15 minutos' in messages[0].text and reset in messages[0].text
    assert 'não confirma uma assinatura' in messages[1].text
    assert 'https://burger.staging.fomizero.com.br/login?redirect=/subscriptions' in messages[1].text
    assert 'token=' not in messages[1].html and 'sck=' not in messages[1].html
    assert 'foi alterada' in messages[2].subject and reset not in messages[2].html


def test_cid_png_and_resend_multipart_payload(monkeypatch):
    monkeypatch.setenv('RESEND_API_KEY','synthetic-api-key')
    message=mail.recovery_message('Gabriel','MeuBurger','https://burger.fomizero.com.br/redefinir-senha#token=sample')
    captured=[]
    import httpx
    def send(self,url,headers,json):
        captured.append(json)
        assert url=='https://api.resend.com/emails' and headers['Authorization']=='Bearer synthetic-api-key'
        return httpx.Response(200,json={'id':'test-id'})
    monkeypatch.setattr(httpx.Client,'post',send)
    assert mail.send_email('owner@example.com',message)=='accepted'
    payload=captured[0]
    assert payload['html']==message.html and payload['text']==message.text
    image=payload['attachments'][0]
    assert image['content_id']==mail.LOGO_CID and image['content_type']=='image/png'
    assert base64.b64decode(image['content']).startswith(b'\x89PNG\r\n\x1a\n')


def test_resend_rejection_logs_safe_reason_without_recipient(monkeypatch, caplog):
    monkeypatch.setenv('RESEND_API_KEY', 'synthetic-api-key')
    message = mail.welcome_message('Gabriel', 'Loja', 'burger')
    import httpx
    def reject(self, url, headers, json):
        assert '/' not in headers['Idempotency-Key']
        return httpx.Response(400, json={'name': 'validation_error',
            'message': 'Idempotency key invalid for owner@example.com'})
    monkeypatch.setattr(httpx.Client, 'post', reject)
    assert mail.send_email('owner@example.com', message, idempotency_key='welcome-1-1-0') == 'failed'
    assert 'status=400 name=validation_error category=idempotency' in caplog.text
    assert 'owner@example.com' not in caplog.text and 'synthetic-api-key' not in caplog.text


def test_welcome_sent_only_after_success_and_failure_does_not_undo_signup(client,sessions,monkeypatch):
    mock_captcha(monkeypatch)
    monkeypatch.setenv('RESEND_API_KEY','synthetic-key')
    sent=[]
    def fail(address,message,**kwargs):
        # New session sees a committed store/user before dispatch.
        with sessions() as db:assert db.query(AdminUser).filter_by(email=address).one().id
        sent.append(message)
        assert '/' not in kwargs['idempotency_key']
        return 'failed'
    monkeypatch.setattr(mail,'send_email',fail)
    response=enroll(client,plan_code='essential')
    assert response.status_code==201 and response.json()['checkout_url']
    assert len(sent)==1 and 'Bem-vindo' in sent[0].subject
    with sessions() as db:
        audit=db.query(AdminAuditLog).filter_by(action='email.welcome').one()
        assert json.loads(audit.meta_json)=={'delivery':'failed'}
    assert enroll(client,plan_code='unavailable').status_code==400
    assert len(sent)==1


def test_owner_resend_reports_provider_failure_then_success(sessions, monkeypatch):
    from app.core import config
    from app.routers.admin_auth import router
    monkeypatch.setenv('RESEND_API_KEY', 'synthetic-key')
    monkeypatch.setenv('PUBLIC_SIGNUP_ORIGINS', 'https://fomizero.com.br')
    monkeypatch.setattr(config, 'ADMIN_SESSION_SECRET', 'synthetic-session-secret')
    with sessions() as db, db.begin():
        owner = db.get(AdminUser, 1)
        owner.email_verification_required = True
        owner.email_verified_at = None
        owner.email_verification_sent_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    app = FastAPI(); app.include_router(router)
    def database():
        with sessions() as db: yield db
    def actor():
        with sessions() as db: return db.get(AdminUser, 1)
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_admin_user] = actor
    delivered = []
    def send(address, message, **kwargs):
        delivered.append(kwargs['idempotency_key'])
        return 'failed' if len(delivered) == 1 else 'accepted'
    monkeypatch.setattr(mail, 'send_email', send)
    with TestClient(app) as http:
        first = http.post('/api/admin/auth/email-verification/resend', headers={'X-Email-Action': '1'})
        assert first.status_code == 502, first.text
        with sessions() as db, db.begin():
            db.get(AdminUser, 1).email_verification_sent_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        second = http.post('/api/admin/auth/email-verification/resend', headers={'X-Email-Action': '1'})
        assert second.status_code == 202, second.text
    assert len(delivered) == 2 and all('/' not in key for key in delivered)


def test_administrative_password_change_sends_notice_after_commit(sessions,monkeypatch):
    from app.routers.admin_users import router
    from app.deps import require_admin_user
    monkeypatch.setenv('RESEND_API_KEY','synthetic-key')
    monkeypatch.setenv('PASSWORD_RESET_BASE_DOMAIN','fomizero.com.br')
    with sessions() as db,db.begin():db.get(AdminUser,1).role='admin'
    app=FastAPI();app.include_router(router)
    def database():
        with sessions() as db:yield db
    def actor():
        with sessions() as db:return db.get(AdminUser,1)
    app.dependency_overrides[get_db]=database
    app.dependency_overrides[require_admin_user]=actor
    sent=[]
    def send(address,message,**kwargs):
        with sessions() as db:assert db.get(AdminUser,1).credential_version==1
        sent.append(message);return 'accepted'
    monkeypatch.setattr(mail,'send_email',send)
    with TestClient(app) as client:
        response=client.post('/api/admin/users/1/reset_password?tenant_id=1',json={'new_password':'new-password-123'})
    assert response.status_code==200,response.text
    assert len(sent)==1 and 'foi alterada' in sent[0].subject
    assert 'new-password-123' not in sent[0].html
