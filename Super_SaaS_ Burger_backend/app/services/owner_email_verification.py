"""Optional, post-signup proof of a public store owner's email address."""
from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
from urllib.parse import urlsplit

from fastapi import HTTPException
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import func, or_, update

from app.core import config
from app.models.admin_user import AdminUser
from app.models.tenant import Tenant
from app.services.admin_audit import log_admin_action
from app.services.passwords import verify_password
from app.services.public_signup import public_signup_settings

TOKEN_TTL_SECONDS = 48 * 3600
RESEND_COOLDOWN_SECONDS = 60


def enabled() -> bool:
    return bool(os.getenv("RESEND_API_KEY", "").strip() and config.ADMIN_SESSION_SECRET)


def _serializer():
    if not config.ADMIN_SESSION_SECRET:
        raise HTTPException(503, "Verificação de e-mail temporariamente indisponível")
    return URLSafeTimedSerializer(config.ADMIN_SESSION_SECRET, salt="owner-email-verification-v1",
        signer_kwargs={"digest_method": hashlib.sha256})


def _origin():
    origins = public_signup_settings().origins
    preferred = "https://www.fomizero.com.br"
    if preferred in origins or "https://fomizero.com.br" in origins:
        return preferred
    if not origins:
        raise HTTPException(503, "Origem do cadastro não configurada")
    return origins[0]


def verification_link(user: AdminUser) -> str:
    token = _serializer().dumps({"u": user.id, "t": user.tenant_id,
        "e": user.email.lower(), "n": secrets.token_urlsafe(8)})
    origin = _origin()
    if urlsplit(origin).scheme != "https":
        raise HTTPException(503, "Origem do cadastro inválida")
    return f"{origin}/verificar-email#token={token}"


def verify(db, token: str):
    try:
        value = _serializer().loads(token, max_age=TOKEN_TTL_SECONDS)
        if (not isinstance(value, dict) or set(value) != {"u", "t", "e", "n"}
            or type(value["u"]) is not int or type(value["t"]) is not int
            or not isinstance(value["e"], str) or not isinstance(value["n"], str)):
            raise ValueError()
    except (BadSignature, ValueError, TypeError):
        raise HTTPException(400, "Link inválido ou expirado. Solicite outro no painel da loja.") from None
    user = db.query(AdminUser).filter_by(id=value["u"], tenant_id=value["t"], active=True,
        email_verification_required=True).with_for_update().populate_existing().one_or_none()
    tenant = db.query(Tenant).filter_by(id=value["t"], is_active=True).one_or_none()
    if not user or not tenant or user.role != "owner" or user.email.lower() != value["e"]:
        raise HTTPException(400, "Link inválido ou expirado. Solicite outro no painel da loja.")
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(timezone.utc)
        log_admin_action(db, tenant_id=user.tenant_id, user_id=None, actor_type="system",
            action="onboarding.owner_email_verified", entity_type="admin_user", entity_id=user.id)
        db.commit()
    return {"slug": tenant.slug, "verified": True}


def reserve_resend(db, user: AdminUser) -> datetime | None:
    if not enabled():
        raise HTTPException(503, "Envio de e-mail temporariamente indisponível")
    if user.role != "owner" or not user.email_verification_required:
        raise HTTPException(403, "Verificação não disponível para este usuário")
    if user.email_verified_at is not None:
        return None
    now = datetime.now(timezone.utc)
    reserved = db.execute(update(AdminUser).where(AdminUser.id == user.id,
        AdminUser.email_verified_at.is_(None),
        or_(AdminUser.email_verification_sent_at.is_(None),
            AdminUser.email_verification_sent_at < now - timedelta(seconds=RESEND_COOLDOWN_SECONDS)))
        .values(email_verification_sent_at=now).execution_options(synchronize_session=False))
    db.commit()
    return now if reserved.rowcount == 1 else None


def change_unverified_email(db, user: AdminUser, new_email: str, password: str):
    if not enabled():
        raise HTTPException(503, "Envio de e-mail temporariamente indisponível")
    user = db.query(AdminUser).filter_by(id=user.id, tenant_id=user.tenant_id, active=True) \
        .with_for_update().populate_existing().one_or_none()
    if user is None:
        raise HTTPException(403, "Alteração indisponível nesta etapa")
    if user.role != "owner" or not user.email_verification_required or user.email_verified_at is not None:
        raise HTTPException(403, "Alteração indisponível nesta etapa")
    if not verify_password(password, user.password_hash):
        raise HTTPException(403, "Não foi possível confirmar a senha")
    normalized = new_email.strip().lower()
    if normalized == user.email.lower():
        raise HTTPException(400, "Informe um e-mail diferente")
    if db.query(AdminUser.id).filter(AdminUser.tenant_id == user.tenant_id,
        func.lower(AdminUser.email) == normalized).first():
        raise HTTPException(409, "Não foi possível usar este e-mail")
    from app.core.stripe_config import stripe_settings
    from app.models.subscription import Subscription
    from app.services.stripe_billing import stripe_request
    from app.services.billing_common import BillingError
    sub = db.query(Subscription).filter_by(tenant_id=user.tenant_id, provider="stripe").one_or_none()
    if sub and sub.provider_customer_id:
        try:
            stripe_request(stripe_settings(), "POST", "customers/" + sub.provider_customer_id,
                data={"email": normalized}, idempotency_key=f"fomizero-customer-email-{user.id}-{hashlib.sha256(normalized.encode()).hexdigest()[:24]}")
        except BillingError:
            raise HTTPException(503, "Não foi possível atualizar o e-mail de cobrança. Tente novamente.") from None
    user.email = normalized
    user.email_verification_sent_at = datetime.now(timezone.utc)
    log_admin_action(db, tenant_id=user.tenant_id, user_id=user.id,
        action="onboarding.owner_email_corrected", entity_type="admin_user", entity_id=user.id)
    db.commit()
    return True
