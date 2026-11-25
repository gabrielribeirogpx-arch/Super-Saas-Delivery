"""Email proof for native enrollment, separate from browser CAPTCHA and invites."""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import secrets

from fastapi import HTTPException

from app.core import config
from app.core.rate_limiter import InMemoryRateLimiterService
from app.services.onboarding_invites import redeem_signup_token, store_signup_token
from app.services.owner_email_verification import enabled as email_enabled
from app.services.transactional_emails import EmailMessage, send_email

_send_limit = InMemoryRateLimiterService(limit=10, window_seconds=60)
_address_limit = InMemoryRateLimiterService(limit=3, window_seconds=900)


def ready(settings):
    return settings.enrollment_ready and email_enabled()


def _digest(email, code):
    return hmac.new(
        config.ADMIN_SESSION_SECRET.encode(),
        f"native-signup-v1:{email.strip().lower()}:{code}".encode(),
        hashlib.sha256,
    ).hexdigest()


def send_code(db, email, settings):
    if not ready(settings):
        raise HTTPException(503, "Cadastro pelo aplicativo temporariamente indisponível")
    email = email.strip().lower()
    # A fixed number of buckets bounds process memory under email-address rotation.
    bucket = hashlib.sha256(email.encode()).hexdigest()[:3]
    for limiter, key in ((_send_limit, "native-signup"), (_address_limit, bucket)):
        decision = limiter.check(tenant_id=key, endpoint="email-code")
        if not decision.allowed:
            raise HTTPException(429, "Aguarde para solicitar outro código",
                headers={"Retry-After": str(decision.retry_after_seconds)})
    code = base64.b32encode(secrets.token_bytes(10)).decode()
    subject = "Seu código para criar uma loja no Fomizero"
    text = f"Digite {code} no app Fomizero Gestão. O código vale por 15 minutos."
    message = EmailMessage(subject,
        f'<img src="cid:fomizero-logo" width="150" alt="Fomizero"><p>{text}</p>', text)
    store_signup_token(db, _digest(email, code), datetime.now(timezone.utc) + timedelta(minutes=15))
    if send_email(email, message) != "accepted":
        db.rollback()
        raise HTTPException(503, "Não foi possível enviar o código agora")
    db.commit()


def verify(db, payload, code, settings):
    if not ready(settings):
        raise HTTPException(503, "Cadastro pelo aplicativo temporariamente indisponível")
    if payload.custom_domain:
        raise HTTPException(400, "Configure seu domínio após contratar um plano compatível")
    if not payload.accept_terms or payload.terms_version != settings.terms_version:
        raise HTTPException(400, "Leia e aceite os termos atuais para continuar")
    code = code.strip().upper()
    if not re.fullmatch(r"[A-Z2-7]{16}", code) or not redeem_signup_token(
        db, _digest(payload.admin_email, code), datetime.now(timezone.utc)
    ):
        raise HTTPException(401, "Código inválido ou expirado. Solicite outro no aplicativo.")
