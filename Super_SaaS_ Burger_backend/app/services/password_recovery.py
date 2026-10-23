"""Audience-scoped administrative and driver recovery. No tokens/addresses/provider payloads in logs."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets
from urllib.parse import urlencode

import httpx
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import func, or_, update
from fastapi import HTTPException
from app.core import config
from app.core.domains import is_reserved_platform_subdomain
from app.models.admin_user import AdminUser
from app.models.tenant import Tenant
from app.services.passwords import hash_password
from app.services.admin_audit import log_admin_action
from app.services.transactional_emails import base_domain, recovery_message, send_email
from app.services.admin_login_attempts import clear_login_attempts

TTL = 900
MESSAGE = 'Se os dados corresponderem a uma conta ativa, enviaremos um link de recuperação. Aguarde alguns minutos e confira também o spam.'


def serializer(audience="admin"):
    if audience not in {"admin", "driver"}:
        raise ValueError("Invalid recovery audience")
    if not config.ADMIN_SESSION_SECRET:
        raise HTTPException(503, 'Recuperação de acesso temporariamente indisponível')
    return URLSafeTimedSerializer(config.ADMIN_SESSION_SECRET, salt=f'{audience}-password-reset-v1', signer_kwargs={'digest_method': hashlib.sha256})


def ready():
    if not os.getenv('RESEND_API_KEY', '').strip():
        raise HTTPException(503, 'Recuperação de acesso temporariamente indisponível')
    if os.getenv('ENV', '').lower() == 'staging' and not os.getenv('PASSWORD_RESET_BASE_DOMAIN'):
        raise HTTPException(503, 'Configure o domínio de recuperação do staging')
    serializer(); base_domain()


def request_recovery(db, slug, email, audience="admin"):
    ready()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    tenant = db.query(Tenant).filter_by(slug=slug, is_active=True).one_or_none()
    if tenant is None or is_reserved_platform_subdomain(slug):
        return
    user = db.query(AdminUser).filter(AdminUser.tenant_id == tenant.id, func.lower(AdminUser.email) == email.lower(),
        AdminUser.active.is_(True),
        func.lower(AdminUser.role).in_(['delivery','driver']) if audience == 'driver' else func.lower(AdminUser.role).notin_(['delivery','driver'])).one_or_none()
    if user is None:
        return
    # Atomic DB cooldown across processes, reserved before outbound HTTP.
    reserved = db.execute(update(AdminUser).where(AdminUser.id == user.id,
        or_(AdminUser.recovery_sent_at.is_(None), AdminUser.recovery_sent_at < now - timedelta(seconds=60)))
        .values(recovery_sent_at=now).execution_options(synchronize_session=False))
    if reserved.rowcount != 1:
        db.rollback(); return
    uid, tid, address, version = user.id, user.tenant_id, user.email, user.credential_version or 0
    db.commit()
    token = serializer(audience).dumps({'u':uid, 't':tid, 'v':version, 'p':hmac.new(config.ADMIN_SESSION_SECRET.encode(), user.password_hash.encode(), hashlib.sha256).hexdigest(), 'n':secrets.token_urlsafe(16)})
    path = '/driver/redefinir-senha' if audience == 'driver' else '/redefinir-senha'
    link = f'https://{slug}.{base_domain()}{path}#' + urlencode({'token':token})
    message = recovery_message(user.name,tenant.business_name,link,driver=audience == "driver")
    delivery = send_email(address,message)
    log_admin_action(db,tenant_id=tid,user_id=None,actor_type='system',action='auth.recovery_requested',entity_type='admin_user',entity_id=uid,
        meta={'delivery':delivery})
    db.commit()
    # Same public response even for provider errors, cooldown or unknown users.


def reset_password(db, token, password, slug=None, audience="admin"):
    try:
        value = serializer(audience).loads(token, max_age=TTL)
        if not isinstance(value,dict) or set(value) != {'u','t','v','p','n'} or any(type(value[k]) is not int for k in ('u','t','v')):
            raise ValueError()
    except (BadSignature, ValueError, TypeError):
        raise HTTPException(400, 'Link inválido ou expirado. Solicite um novo link.') from None
    user = db.query(AdminUser).filter_by(id=value['u'],tenant_id=value['t'],active=True).one_or_none()
    tenant = db.query(Tenant).filter_by(id=value['t'],is_active=True).one_or_none()
    if (user is None or tenant is None or (slug is not None and slug != tenant.slug)
        or ((user.role.lower() in {'driver','delivery'}) != (audience == 'driver'))):
        raise HTTPException(400, 'Link inválido ou expirado. Solicite um novo link.')
    expected = hmac.new(config.ADMIN_SESSION_SECRET.encode(), user.password_hash.encode(), hashlib.sha256).hexdigest()
    if not isinstance(value['p'],str) or not hmac.compare_digest(value['p'],expected):
        raise HTTPException(400, 'Link inválido ou expirado. Solicite um novo link.')
    changed = db.execute(update(AdminUser).where(AdminUser.id == user.id,AdminUser.active.is_(True),AdminUser.credential_version == value['v'],AdminUser.password_hash == user.password_hash)
        .values(password_hash=hash_password(password),credential_version=value['v']+1)
        .execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(400, 'Link inválido ou expirado. Solicite um novo link.')
    clear_login_attempts(db,user.tenant_id,user.email)
    log_admin_action(db,tenant_id=user.tenant_id,user_id=user.id,action='auth.password_reset',entity_type='admin_user',entity_id=user.id)
    db.commit()
    return {"slug":tenant.slug,"user_id":user.id,"tenant_id":user.tenant_id,"version":value["v"]+1}
