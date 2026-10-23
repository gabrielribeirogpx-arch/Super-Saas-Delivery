"""Three transactional messages. No promotional tracking or credentials in audit."""
from dataclasses import dataclass
from functools import lru_cache
from html import escape
from pathlib import Path
import base64
import logging
import os
import re
import secrets
import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.admin_user import AdminUser
from app.models.tenant import Tenant
from app.services.admin_audit import log_admin_action

LOGO_CID = 'fomizero-logo'
LOGO_PATH = Path(__file__).resolve().parents[1] / 'assets' / 'fomizero-email-logo.png'

@dataclass(frozen=True, repr=False)
class EmailMessage:
    subject: str
    html: str
    text: str


def base_domain():
    value = os.getenv('PASSWORD_RESET_BASE_DOMAIN', 'fomizero.com.br').strip().lower()
    if (os.getenv('ENV', '').lower() == 'staging' and not os.getenv('PASSWORD_RESET_BASE_DOMAIN')) or not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', value):
        raise HTTPException(503, 'Configure o domínio de acesso deste ambiente')
    return value


def store_url(slug, path):
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?', slug):
        raise ValueError('Invalid store address')
    return f'https://{slug}.{base_domain()}{path}'


def support_email():
    value = os.getenv('SALES_SUPPORT_EMAIL', '').strip()
    return value if re.fullmatch(r'[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}',value) else None


def layout(*, name, store, title, intro, button, url, notice, details, subject):
    # All personal/customer-controlled values are escaped. URLs come from our
    # configured platform domain; caller never supplies a redirect from HTTP input.
    store = store or 'Sua loja'
    first = (name or '').strip().split()[0] if (name or '').strip() else 'olá'
    greeting = f'Olá, {first}!' if first != 'olá' else 'Olá!'
    help_address = support_email()
    support_html = f'<p style="margin:12px 0 0">Precisa de ajuda? <a href="mailto:{escape(help_address)}" style="color:#b91c1c">Fale com o suporte</a>.</p>' if help_address else ''
    support_text = f'\nSuporte: {help_address}' if help_address else ''
    html = f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(subject)}</title></head>
<body style="margin:0;padding:0;background:#f5f6f8;color:#182132;font-family:Arial,Helvetica,sans-serif">
<div style="display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all">{escape(title)} · Fomizero</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f5f6f8"><tr><td align="center" style="padding:32px 12px">
<table role="presentation" width="560" cellspacing="0" cellpadding="0" style="width:100%;max-width:560px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px"><tr><td style="padding:32px 24px">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding-bottom:28px"><img src="cid:{LOGO_CID}" width="210" height="55" alt="Fomizero Delivery" style="display:block;width:210px;max-width:100%;height:auto;border:0"></td></tr></table>
<p style="margin:0 0 12px;font-size:15px;color:#475569">{escape(greeting)}</p>
<h1 style="margin:0 0 16px;font-size:26px;line-height:1.25;color:#182132">{escape(title)}</h1>
<p style="margin:0 0 20px;font-size:16px;line-height:1.65">{escape(intro)}</p>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 24px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px"><tr><td style="padding:14px 16px;word-break:break-word"><span style="font-size:12px;color:#64748b">SUA LOJA</span><br><strong style="font-size:16px;line-height:1.6">{escape(store)}</strong></td></tr></table>
<table role="presentation" cellspacing="0" cellpadding="0" style="margin:0 0 24px"><tr><td bgcolor="#dc2626" style="border-radius:8px;mso-padding-alt:16px 24px"><a href="{escape(url,quote=True)}" style="display:inline-block;padding:16px 24px;color:#ffffff;background:#dc2626;border-radius:8px;font-size:15px;font-weight:bold;text-decoration:none;text-align:center">{escape(button)}</a></td></tr></table>
<p style="margin:0 0 16px;font-size:14px;line-height:1.65;color:#475569">{escape(notice)}</p>
<p style="margin:0 0 24px;font-size:14px;line-height:1.65;color:#475569">{escape(details)}</p>
<hr style="border:0;border-top:1px solid #e2e8f0;margin:24px 0">
<p style="font-size:12px;line-height:1.65;color:#64748b;margin:0">Se o botão não abrir, copie e cole este endereço no navegador:</p>
<p style="font-size:12px;line-height:1.65;word-break:break-all;overflow-wrap:anywhere;margin:8px 0 0"><a href="{escape(url,quote=True)}" style="color:#b91c1c">{escape(url)}</a></p>
</td></tr></table>
<table role="presentation" width="560" cellspacing="0" cellpadding="0" style="width:100%;max-width:560px"><tr><td align="center" style="padding:20px 16px;font-size:12px;line-height:1.65;color:#64748b">Mensagem automática do Fomizero. Nunca compartilhe sua senha.{support_html}</td></tr></table>
</td></tr></table></body></html>'''
    text = f'{greeting}\n\n{title}\nLoja: {store}\n\n{intro}\n\n{button}:\n{url}\n\n{notice}\n\n{details}\n\nMensagem automática do Fomizero. Nunca compartilhe sua senha.{support_text}'
    return EmailMessage(subject,html,text)


def recovery_message(name,store,url,*,driver=False):
    return layout(name=name,store=store,title='Vamos recuperar seu acesso?',
        intro=('Recebemos uma solicitação para criar uma nova senha da área do entregador.' if driver else 'Recebemos uma solicitação para criar uma nova senha de acesso à sua loja.'),
        button='Criar nova senha',url=url,notice='Este link vale por 15 minutos e pode ser usado uma única vez.',
        details='Se não foi você, pode ignorar esta mensagem. Sua senha continua a mesma. Nunca compartilhe este link.',
        subject='Redefina sua senha no Fomizero')


def welcome_message(name,store,slug):
    url=store_url(slug,'/login?redirect=/subscriptions')
    return layout(name=name,store=store,title='Sua loja já tem um endereço!',
        intro='Seu cadastro no Fomizero foi concluído. Guarde este e-mail para encontrar sua loja quando precisar.',
        button='Acessar minha loja',url=url,notice='Entre com o e-mail e a senha que você cadastrou. No painel, você pode consultar sua assinatura e continuar a contratação.',
        details='Criar a loja não confirma uma assinatura. Os recursos pagos são liberados após a confirmação do pagamento. Depois, configure os dados da loja, produtos e preços e confira a prévia do cardápio.',
        subject='Bem-vindo ao Fomizero — guarde o acesso à sua loja')


def password_changed_message(name,store,slug,*,driver=False):
    return layout(name=name,store=store,title='Sua senha foi alterada',
        intro=('Confirmamos a redefinição da senha da área do entregador no Fomizero.' if driver else 'Confirmamos a redefinição da senha de acesso à sua loja no Fomizero.'),
        button='Entrar na área do entregador' if driver else 'Entrar na minha loja',url=store_url(slug,'/driver/login' if driver else '/login'),
        notice='Use sua nova senha para entrar. As sessões anteriores precisarão de um novo login na próxima verificação de acesso.',
        details='Se você não reconhece esta alteração, abra o login pelo endereço da sua loja e use “Esqueci minha senha” para recuperar o acesso. Procure o suporte se precisar de ajuda.',
        subject='Sua senha do Fomizero foi alterada')


@lru_cache(maxsize=1)
def logo_content():
    return base64.b64encode(LOGO_PATH.read_bytes()).decode('ascii')


def send_email(address, message, *, idempotency_key=None):
    key=os.getenv('RESEND_API_KEY','').strip()
    if not key:
        return 'skipped'
    payload={'from':'Fomizero <acesso@fomizero.com.br>','to':[address], 'subject':message.subject,
        'html':message.html,'text':message.text,'attachments':[{'filename':'fomizero.png','content':logo_content(),
            'content_type':'image/png','content_id':LOGO_CID}]}
    if support_email():payload['reply_to']=support_email()
    try:
        with httpx.Client(timeout=8,follow_redirects=False) as client:
            response=client.post('https://api.resend.com/emails',headers={'Authorization':'Bearer '+key,
                'Idempotency-Key':idempotency_key or secrets.token_urlsafe(24)},json=payload)
        return 'accepted' if response.status_code in {200,201,202} else 'failed'
    except httpx.HTTPError:
        return 'failed'


def deliver_account_message(engine, kind, user_id, tenant_id, version=None):
    """Called only after commit. Failures never turn signup/reset into an error."""
    if not os.getenv('RESEND_API_KEY','').strip():return
    try:
        with Session(bind=engine) as db:
            user=db.query(AdminUser).filter_by(id=user_id,tenant_id=tenant_id,active=True).one_or_none()
            tenant=db.query(Tenant).filter_by(id=tenant_id,is_active=True).one_or_none()
            if not user or not tenant:return
            if kind=='welcome':message=welcome_message(user.name,tenant.business_name,tenant.slug)
            elif kind=='password_changed':message=password_changed_message(user.name,tenant.business_name,tenant.slug,driver=user.role.lower() in {"driver","delivery"})
            else:raise ValueError('Unknown transactional message')
            delivery=send_email(user.email,message,idempotency_key=f'{kind}/{tenant_id}/{user_id}/{version or 0}')
            log_admin_action(db,tenant_id=tenant_id,user_id=None,actor_type='system',action='email.'+kind,
                entity_type='admin_user',entity_id=user_id,meta={'delivery':delivery})
            db.commit()
    except Exception:
        logging.getLogger(__name__).error('Transactional email task failed; details omitted')
