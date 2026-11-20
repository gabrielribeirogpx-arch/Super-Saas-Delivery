from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import ENV_NORMALIZED, IS_PROD, IS_STAGE, JWT_SECRET_KEY
from app.core.database import get_db
from app.models.customer import Customer
from app.models.customer_otp import CustomerOtp
from app.models.customer_email_otp import CustomerEmailOtp
from app.models.customer_email_account import CustomerEmailAccount
from app.models.order import Order
from app.models.tenant import Tenant
from app.services.auth import create_access_token, decode_access_token
from app.services.tenant_resolver import TenantResolver
from app.services.transactional_emails import EmailMessage, send_email

def private_response(response: Response):
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Vary"] = "Cookie"


router = APIRouter(prefix="/api/public/customer-auth", tags=["public-customer-auth"], dependencies=[Depends(private_response)])
COOKIE_NAME = "customer_session"
OTP_TTL_MINUTES = 7
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_MAX_ATTEMPTS = 5
OTP_MAX_REQUESTS_PER_HOUR = 10
CUSTOMER_SESSION_MINUTES = 24 * 60


class RequestCodePayload(BaseModel):
    phone: str = Field(..., min_length=8, max_length=32)
    accepted_terms: bool = False
    marketing_consent: bool = False


class VerifyCodePayload(BaseModel):
    phone: str = Field(..., min_length=8, max_length=32)
    code: str = Field(..., pattern=r"^\d{6}$")


class RequestEmailCodePayload(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    accepted_terms: bool = False


class VerifyEmailCodePayload(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    code: str = Field(..., pattern=r"^\d{6}$")


def normalize_email(email: str) -> str:
    value = (email or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+", value) or len(value) > 254:
        raise HTTPException(status_code=422, detail="E-mail inválido")
    return value


def mask_email(email: str) -> str:
    name, domain = email.split("@", 1)
    return f"{name[:1]}***@{domain}"


def email_otp_hash(code: str, email: str, tenant_id: int) -> str:
    if not JWT_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Acesso à conta temporariamente indisponível")
    return hmac.new(JWT_SECRET_KEY.encode(), f"email:{tenant_id}:{email}:{code}".encode(), hashlib.sha256).hexdigest()


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D+", "", phone or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) in (10, 11):
        digits = "55" + digits
    if not digits.startswith("55") or len(digits) not in (12, 13):
        raise HTTPException(status_code=422, detail="Telefone inválido")
    return f"+{digits}"


def phone_variants(phone: str) -> set[str]:
    canonical = normalize_phone(phone)
    return {canonical, canonical[1:], canonical[3:]}


def mask_phone(phone: str) -> str:
    return f"{phone[:3]}******{phone[-2:]}"


def otp_hash(code: str, phone: str, tenant_id: int) -> str:
    if not JWT_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Acesso à conta temporariamente indisponível")
    return hmac.new(JWT_SECRET_KEY.encode(), f"{tenant_id}:{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def resolve_tenant(request: Request, db: Session):
    tenant = TenantResolver.resolve_tenant_from_request(db, request)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    return tenant


class CustomerOtpProvider:
    def send_code(self, *, tenant_name: str, phone: str, code: str) -> None:
        raise NotImplementedError


class TestCustomerOtpProvider(CustomerOtpProvider):
    def send_code(self, *, tenant_name: str, phone: str, code: str) -> None:
        if ENV_NORMALIZED != "test":
            raise RuntimeError("Test OTP provider is restricted to automated tests")
        # Tests inject/capture delivery in memory. Never log or return the code.


def provider() -> CustomerOtpProvider:
    if ENV_NORMALIZED == "test" and os.getenv("CUSTOMER_OTP_PROVIDER", "").lower() == "test":
        return TestCustomerOtpProvider()
    # No real delivery integration has been configured. Fail closed instead of
    # creating a usable OTP and claiming a message was sent.
    raise HTTPException(status_code=503, detail="Acesso por código ainda indisponível. Você pode continuar comprando sem cadastro.")


def set_session_cookie(response: Response, token: str):
    response.set_cookie(COOKIE_NAME, token, max_age=CUSTOMER_SESSION_MINUTES * 60,
                        httponly=True, secure=IS_PROD or IS_STAGE, samesite="lax", path="/")


def get_customer_session(request: Request) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Confirme seu telefone para acessar a conta")
    try:
        payload = decode_access_token(token)
        if payload.get("type") != "customer" or payload.get("phone_verified") is not True:
            raise ValueError("Customer verification missing")
        for field in ("tenant_id", "customer_id"):
            if type(payload.get(field)) is not int or payload[field] <= 0:
                raise ValueError("Invalid session scope")
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada") from exc
    return payload


def get_customer_email_session(request: Request, tenant_id: int) -> str:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Confirme seu e-mail para acessar a conta")
    try:
        payload = decode_access_token(token)
        if (payload.get("type") != "customer_email" or payload.get("email_verified") is not True
            or type(payload.get("tenant_id")) is not int or payload["tenant_id"] != tenant_id
            or not isinstance(payload.get("email"), str)):
            raise ValueError("Invalid email session")
        return normalize_email(payload["email"])
    except (ValueError, TypeError, HTTPException) as exc:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada") from exc


def is_customer_email_session(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
    try:
        return decode_access_token(token).get("type") == "customer_email"
    except ValueError:
        return False


def get_verified_customer(request: Request, db: Session, tenant_id: int | None = None) -> Customer:
    session = get_customer_session(request)
    resolved_id = int(resolve_tenant(request, db).id) if tenant_id is None else tenant_id
    if session["tenant_id"] != resolved_id:
        raise HTTPException(status_code=403, detail="Sessão não pertence a esta loja")
    customer = db.query(Customer).filter(Customer.id == session["customer_id"],
        Customer.tenant_id == resolved_id, Customer.is_active.is_(True),
        Customer.phone_verified_at.is_not(None)).first()
    if customer is None:
        raise HTTPException(status_code=401, detail="Confirme seu telefone novamente")
    return customer


@router.post("/request-code")
def request_code(payload: RequestCodePayload, request: Request, db: Session = Depends(get_db)):
    if not payload.accepted_terms:
        raise HTTPException(status_code=422, detail="Aceite os termos para continuar")
    tenant = resolve_tenant(request, db)
    phone = normalize_phone(payload.phone)
    sender = provider()
    now = datetime.now(timezone.utc)
    # Serialize requests within the tenant, including when no prior OTP exists.
    db.query(Tenant).filter(Tenant.id == tenant.id).with_for_update().first()
    previous = db.query(CustomerOtp).filter(CustomerOtp.tenant_id == tenant.id,
        CustomerOtp.phone_normalized == phone)
    latest = previous.order_by(CustomerOtp.created_at.desc(), CustomerOtp.id.desc()).first()
    if latest and latest.created_at.replace(tzinfo=timezone.utc) > now - timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS):
        raise HTTPException(status_code=429, detail="Aguarde um minuto antes de reenviar o código", headers={"Retry-After": "60"})
    if previous.filter(CustomerOtp.created_at > now - timedelta(hours=1)).count() >= OTP_MAX_REQUESTS_PER_HOUR:
        raise HTTPException(status_code=429, detail="Limite de tentativas atingido. Tente mais tarde.")
    previous.filter(CustomerOtp.used_at.is_(None)).update({"used_at": now}, synchronize_session=False)
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(CustomerOtp(tenant_id=tenant.id, phone_normalized=phone, code_hash=otp_hash(code, phone, tenant.id), expires_at=now + timedelta(minutes=OTP_TTL_MINUTES)))
    try:
        sender.send_code(tenant_name=getattr(tenant, "business_name", None) or getattr(tenant, "slug", "Loja"), phone=phone, code=code)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Não foi possível enviar o código. Tente novamente mais tarde.") from exc
    return {"ok": True, "expires_in_seconds": OTP_TTL_MINUTES * 60, "retry_after_seconds": OTP_RESEND_COOLDOWN_SECONDS}


@router.post("/verify-code")
def verify_code(payload: VerifyCodePayload, request: Request, response: Response, db: Session = Depends(get_db)):
    provider()  # No verification against unsent/stale codes without a live provider.
    tenant = resolve_tenant(request, db)
    phone = normalize_phone(payload.phone)
    now = datetime.now(timezone.utc)
    otp = db.query(CustomerOtp).filter(CustomerOtp.tenant_id == tenant.id,
        CustomerOtp.phone_normalized == phone, CustomerOtp.used_at.is_(None)).order_by(CustomerOtp.created_at.desc(), CustomerOtp.id.desc()).with_for_update().first()
    if not otp or otp.expires_at.replace(tzinfo=timezone.utc) <= now or otp.attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=401, detail="Código inválido ou expirado")
    otp.attempts += 1
    if not hmac.compare_digest(otp.code_hash, otp_hash(payload.code, phone, tenant.id)):
        db.commit()
        raise HTTPException(status_code=401, detail="Código inválido ou expirado")
    otp.used_at = now
    variants = phone_variants(phone)
    customer = db.query(Customer).filter(Customer.tenant_id == tenant.id,
        or_(Customer.phone_normalized.in_(variants), Customer.phone.in_(variants))).order_by(Customer.id.asc()).first()
    if not customer:
        customer = Customer(tenant_id=tenant.id, name="", phone=phone, phone_normalized=phone, is_active=True)
        db.add(customer)
        db.flush()
    if not customer.is_active:
        raise HTTPException(status_code=403, detail="Conta indisponível")
    customer.phone_verified_at = now
    token = create_access_token(str(customer.id), extra={"type": "customer", "phone_verified": True,
        "customer_id": int(customer.id), "tenant_id": int(tenant.id)}, expires_minutes=CUSTOMER_SESSION_MINUTES)
    db.commit()
    set_session_cookie(response, token)
    return {"ok": True, "customer": {"id": customer.id, "phone_masked": mask_phone(phone), "name": customer.name or None}}


@router.post("/request-email-code")
def request_email_code(payload: RequestEmailCodePayload, request: Request, db: Session = Depends(get_db)):
    if not os.getenv("RESEND_API_KEY", "").strip() or not JWT_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Acesso por e-mail temporariamente indisponível")
    tenant = resolve_tenant(request, db)
    email = normalize_email(payload.email)
    now = datetime.now(timezone.utc)
    db.query(Tenant).filter(Tenant.id == tenant.id).with_for_update().first()
    account = db.query(CustomerEmailAccount).filter(CustomerEmailAccount.tenant_id == tenant.id,
        CustomerEmailAccount.email_normalized == email).first()
    previous = db.query(CustomerEmailOtp).filter(CustomerEmailOtp.tenant_id == tenant.id,
        CustomerEmailOtp.email_normalized == email)
    latest = previous.order_by(CustomerEmailOtp.created_at.desc(), CustomerEmailOtp.id.desc()).first()
    pending_name = None
    pending_phone = None
    if account is None:
        if not payload.accepted_terms:
            raise HTTPException(status_code=422, detail="Aceite os termos para criar a conta")
        recent_signup = latest if latest and latest.created_at.replace(tzinfo=timezone.utc) > now - timedelta(minutes=15) else None
        pending_name = (payload.name or (recent_signup.pending_name if recent_signup else None) or "").strip()
        if len(pending_name) < 2:
            raise HTTPException(status_code=422, detail="Informe seu nome para criar a conta")
        pending_phone = normalize_phone(payload.phone or (recent_signup.pending_phone if recent_signup else None) or "")
    if latest and latest.created_at.replace(tzinfo=timezone.utc) > now - timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS):
        raise HTTPException(status_code=429, detail="Aguarde um minuto antes de reenviar o código", headers={"Retry-After": "60"})
    if previous.filter(CustomerEmailOtp.created_at > now - timedelta(hours=1)).count() >= OTP_MAX_REQUESTS_PER_HOUR:
        raise HTTPException(status_code=429, detail="Limite de tentativas atingido. Tente mais tarde.")
    previous.filter(CustomerEmailOtp.used_at.is_(None)).update({"used_at": now}, synchronize_session=False)
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(CustomerEmailOtp(tenant_id=tenant.id, email_normalized=email,
        pending_name=pending_name, pending_phone=pending_phone,
        code_hash=email_otp_hash(code, email, tenant.id), expires_at=now + timedelta(minutes=OTP_TTL_MINUTES)))
    store_name = getattr(tenant, "business_name", None) or getattr(tenant, "slug", "Loja")
    message = EmailMessage(
        subject=f"Código para acessar seus pedidos em {store_name}",
        html=f"<p>Seu código para acessar os pedidos de {escape(store_name)} é <strong>{code}</strong>.</p><p>Ele expira em {OTP_TTL_MINUTES} minutos. Se você não solicitou, ignore este e-mail.</p>",
        text=f"Seu código para acessar seus pedidos é {code}. Ele expira em {OTP_TTL_MINUTES} minutos. Se você não solicitou, ignore este e-mail.",
    )
    try:
        if send_email(email, message) != "accepted":
            raise RuntimeError("Email delivery unavailable")
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Não foi possível enviar o código. Tente novamente mais tarde.") from exc
    return {"ok": True, "expires_in_seconds": OTP_TTL_MINUTES * 60, "retry_after_seconds": OTP_RESEND_COOLDOWN_SECONDS}


@router.post("/verify-email-code")
def verify_email_code(payload: VerifyEmailCodePayload, request: Request, response: Response, db: Session = Depends(get_db)):
    if not os.getenv("RESEND_API_KEY", "").strip() or not JWT_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Acesso por e-mail temporariamente indisponível")
    tenant = resolve_tenant(request, db)
    email = normalize_email(payload.email)
    now = datetime.now(timezone.utc)
    db.query(Tenant).filter(Tenant.id == tenant.id).with_for_update().first()
    otp = db.query(CustomerEmailOtp).filter(CustomerEmailOtp.tenant_id == tenant.id,
        CustomerEmailOtp.email_normalized == email, CustomerEmailOtp.used_at.is_(None)) \
        .order_by(CustomerEmailOtp.created_at.desc(), CustomerEmailOtp.id.desc()).with_for_update().first()
    if not otp or otp.expires_at.replace(tzinfo=timezone.utc) <= now or otp.attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=401, detail="Código inválido ou expirado")
    otp.attempts += 1
    if not hmac.compare_digest(otp.code_hash, email_otp_hash(payload.code, email, tenant.id)):
        db.commit()
        raise HTTPException(status_code=401, detail="Código inválido ou expirado")
    otp.used_at = now
    account = db.query(CustomerEmailAccount).filter(CustomerEmailAccount.tenant_id == tenant.id,
        CustomerEmailAccount.email_normalized == email).first()
    if account is None:
        if not otp.pending_name or not otp.pending_phone:
            raise HTTPException(status_code=422, detail="Crie seu cadastro antes de acessar a conta")
        account = CustomerEmailAccount(tenant_id=tenant.id, email_normalized=email,
            name=otp.pending_name, phone_normalized=otp.pending_phone, verified_at=now)
        db.add(account)
        variants = phone_variants(otp.pending_phone)
        existing_customer = db.query(Customer.id).filter(Customer.tenant_id == tenant.id,
            or_(Customer.phone_normalized.in_(variants), Customer.phone.in_(variants))).first()
        if existing_customer is None:
            db.add(Customer(tenant_id=tenant.id, name=otp.pending_name, phone=otp.pending_phone,
                phone_normalized=otp.pending_phone, email=email if len(email) <= 150 else None, is_active=True))
    otp.pending_name = None
    otp.pending_phone = None
    token = create_access_token(email, extra={"type": "customer_email", "email_verified": True,
        "email": email, "tenant_id": int(tenant.id)}, expires_minutes=CUSTOMER_SESSION_MINUTES)
    db.commit()
    set_session_cookie(response, token)
    return {"ok": True, "email_masked": mask_email(email), "registered": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/", secure=IS_PROD or IS_STAGE, httponly=True, samesite="lax")
    return {"ok": True}


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    tenant = resolve_tenant(request, db)
    if is_customer_email_session(request):
        email = get_customer_email_session(request, int(tenant.id))
        account = db.query(CustomerEmailAccount).filter(CustomerEmailAccount.tenant_id == tenant.id,
            CustomerEmailAccount.email_normalized == email).first()
        if account is None:
            raise HTTPException(status_code=401, detail="Cadastre sua conta para continuar")
        return {"verification_method": "email", "email_masked": mask_email(email),
            "phone_masked": mask_phone(account.phone_normalized), "name": account.name}
    customer = get_verified_customer(request, db)
    return {"id": customer.id, "name": customer.name, "phone_masked": mask_phone(normalize_phone(customer.phone_normalized or customer.phone)), "phone_verified_at": customer.phone_verified_at, "verification_method": "phone"}


@router.get("/orders")
def orders(request: Request, db: Session = Depends(get_db)):
    tenant = resolve_tenant(request, db)
    if is_customer_email_session(request):
        email = get_customer_email_session(request, int(tenant.id))
        if not db.query(CustomerEmailAccount.id).filter(CustomerEmailAccount.tenant_id == tenant.id,
            CustomerEmailAccount.email_normalized == email).first():
            raise HTTPException(status_code=401, detail="Cadastre sua conta para continuar")
        rows = db.query(Order).filter(Order.tenant_id == tenant.id, Order.customer_email == email) \
            .order_by(Order.created_at.desc(), Order.id.desc()).limit(100).all()
        return [{"order_number": o.daily_order_number or o.id, "tracking_token": o.tracking_token,
            "status": o.status, "total_cents": o.total_cents if o.total_cents is not None else o.valor_total,
            "payment_method": o.payment_method, "delivery_type": o.order_type, "created_at": o.created_at} for o in rows]
    customer = get_verified_customer(request, db)
    # Guest checkout historically stored national digits, country digits or E.164.
    # Resolve equivalent customer rows only after proof of phone possession.
    variants = phone_variants(customer.phone_normalized or customer.phone)
    ids = db.query(Customer.id).filter(Customer.tenant_id == customer.tenant_id,
        or_(Customer.phone_normalized.in_(variants), Customer.phone.in_(variants)))
    rows = db.query(Order).filter(Order.tenant_id == customer.tenant_id, Order.customer_id.in_(ids)).order_by(Order.created_at.desc(), Order.id.desc()).limit(100).all()
    return [{"order_number": o.daily_order_number or o.id, "tracking_token": o.tracking_token,
        "status": o.status, "total_cents": o.total_cents if o.total_cents is not None else o.valor_total,
        "payment_method": o.payment_method, "delivery_type": o.order_type, "created_at": o.created_at} for o in rows]
