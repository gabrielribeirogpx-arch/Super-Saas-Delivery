import base64
import json
from html import escape
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_hotmart_billing import sessions
from test_public_signup import client, mock_captcha, enroll
from app.services import transactional_emails as mail
from app.core.database import get_db
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


def test_welcome_sent_only_after_success_and_failure_does_not_undo_signup(client,sessions,monkeypatch):
    mock_captcha(monkeypatch)
    monkeypatch.setenv('RESEND_API_KEY','synthetic-key')
    sent=[]
    def fail(address,message,**kwargs):
        # New session sees a committed store/user before dispatch.
        with sessions() as db:assert db.query(AdminUser).filter_by(email=address).one().id
        sent.append(message)
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
