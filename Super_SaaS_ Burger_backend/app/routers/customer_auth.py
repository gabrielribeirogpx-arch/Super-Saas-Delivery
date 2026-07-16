from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import IS_PROD, JWT_SECRET_KEY
from app.core.database import get_db
from app.models.customer import Customer
from app.models.customer_otp import CustomerOtp
from app.models.order import Order
from app.services.auth import create_access_token, decode_access_token
from app.services.tenant_resolver import TenantResolver

router = APIRouter(prefix="/api/public/customer-auth", tags=["public-customer-auth"])
COOKIE_NAME = "customer_session"
OTP_TTL_MINUTES = int(os.getenv("CUSTOMER_OTP_TTL_MINUTES", "7"))
OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv("CUSTOMER_OTP_RESEND_COOLDOWN_SECONDS", "60"))
OTP_MAX_ATTEMPTS = int(os.getenv("CUSTOMER_OTP_MAX_ATTEMPTS", "5"))
CUSTOMER_SESSION_MINUTES = int(os.getenv("CUSTOMER_SESSION_MINUTES", "43200"))
TEST_PROVIDER = os.getenv("CUSTOMER_OTP_PROVIDER", "").strip().lower() == "test"

class RequestCodePayload(BaseModel):
    phone: str = Field(..., min_length=8, max_length=32)
    accepted_terms: bool = True
    marketing_consent: bool = False

class VerifyCodePayload(BaseModel):
    phone: str = Field(..., min_length=8, max_length=32)
    code: str = Field(..., min_length=6, max_length=6)


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D+", "", phone or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) in (10, 11):
        digits = "55" + digits
    if not digits.startswith("55") or len(digits) not in (12, 13):
        raise HTTPException(status_code=422, detail="Telefone inválido")
    return f"+{digits}"


def mask_phone(phone: str) -> str:
    return f"{phone[:3]}******{phone[-2:]}"


def otp_hash(code: str, phone: str, tenant_id: int) -> str:
    secret = JWT_SECRET_KEY or os.getenv("CUSTOMER_OTP_SECRET", "dev-insecure-secret")
    return hmac.new(secret.encode(), f"{tenant_id}:{phone}:{code}".encode(), hashlib.sha256).hexdigest()


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
        if IS_PROD:
            raise RuntimeError("Test OTP provider disabled in production")
        print(f"customer_otp_test tenant={tenant_name} phone={mask_phone(phone)} code={code}")

class NullCustomerOtpProvider(CustomerOtpProvider):
    def send_code(self, *, tenant_name: str, phone: str, code: str) -> None:
        # Placeholder for WhatsApp Cloud API/SMS provider. Never logs the code.
        return None


def provider() -> CustomerOtpProvider:
    return TestCustomerOtpProvider() if TEST_PROVIDER and not IS_PROD else NullCustomerOtpProvider()


def set_session_cookie(response: Response, token: str):
    response.set_cookie(COOKIE_NAME, token, max_age=CUSTOMER_SESSION_MINUTES * 60, httponly=True, secure=IS_PROD, samesite="lax", path="/")


def get_customer_session(request: Request) -> dict:
    token = request.cookies.get(COOKIE_NAME) or (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Sessão de cliente necessária")
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Sessão inválida") from exc
    if payload.get("type") != "customer":
        raise HTTPException(status_code=401, detail="Sessão de cliente necessária")
    return payload

@router.post("/request-code")
def request_code(payload: RequestCodePayload, request: Request, db: Session = Depends(get_db)):
    if not payload.accepted_terms:
        raise HTTPException(status_code=422, detail="Aceite os termos para continuar")
    tenant = resolve_tenant(request, db)
    phone = normalize_phone(payload.phone)
    now = datetime.now(timezone.utc)
    latest = db.query(CustomerOtp).filter(CustomerOtp.tenant_id == tenant.id, CustomerOtp.phone_normalized == phone, CustomerOtp.used_at.is_(None)).order_by(CustomerOtp.created_at.desc()).first()
    if latest and latest.created_at and latest.created_at.replace(tzinfo=timezone.utc) > now - timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS):
        return {"ok": True, "message": "Se o telefone for válido, enviaremos um código.", "retry_after_seconds": OTP_RESEND_COOLDOWN_SECONDS}
    db.query(CustomerOtp).filter(CustomerOtp.tenant_id == tenant.id, CustomerOtp.phone_normalized == phone, CustomerOtp.used_at.is_(None)).update({"used_at": now})
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(CustomerOtp(tenant_id=tenant.id, phone_normalized=phone, code_hash=otp_hash(code, phone, tenant.id), expires_at=now + timedelta(minutes=OTP_TTL_MINUTES)))
    provider().send_code(tenant_name=getattr(tenant, "name", None) or getattr(tenant, "business_name", None) or getattr(tenant, "slug", "Loja"), phone=phone, code=code)
    db.commit()
    body = {"ok": True, "message": "Se o telefone for válido, enviaremos um código.", "expires_in_seconds": OTP_TTL_MINUTES * 60}
    if TEST_PROVIDER and not IS_PROD:
        body["test_code"] = code
    return body

@router.post("/verify-code")
def verify_code(payload: VerifyCodePayload, request: Request, response: Response, db: Session = Depends(get_db)):
    tenant = resolve_tenant(request, db)
    phone = normalize_phone(payload.phone)
    now = datetime.now(timezone.utc)
    otp = db.query(CustomerOtp).filter(CustomerOtp.tenant_id == tenant.id, CustomerOtp.phone_normalized == phone, CustomerOtp.used_at.is_(None)).order_by(CustomerOtp.created_at.desc()).first()
    if not otp or otp.expires_at.replace(tzinfo=timezone.utc) < now or otp.attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=401, detail="Código inválido ou expirado")
    otp.attempts += 1
    if not hmac.compare_digest(otp.code_hash, otp_hash(payload.code, phone, tenant.id)):
        db.commit()
        raise HTTPException(status_code=401, detail="Código inválido ou expirado")
    otp.used_at = now
    customer = db.query(Customer).filter(Customer.tenant_id == tenant.id, Customer.phone_normalized == phone).first()
    if not customer:
        customer = Customer(tenant_id=tenant.id, name="", phone=phone, phone_normalized=phone, phone_verified_at=now, is_active=True)
        db.add(customer); db.flush()
    else:
        customer.phone_verified_at = now; customer.is_active = True
    token = create_access_token(str(customer.id), extra={"type": "customer", "customer_id": int(customer.id), "tenant_id": int(tenant.id)}, expires_minutes=CUSTOMER_SESSION_MINUTES)
    set_session_cookie(response, token)
    db.commit()
    return {"ok": True, "access_token": token, "token_type": "bearer", "customer": {"id": customer.id, "phone_masked": mask_phone(phone), "name": customer.name or None}}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}

@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    session = get_customer_session(request)
    tenant = resolve_tenant(request, db)
    if int(session["tenant_id"]) != int(tenant.id):
        raise HTTPException(status_code=403, detail="Tenant inválido")
    customer = db.query(Customer).filter(Customer.id == int(session["customer_id"]), Customer.tenant_id == int(tenant.id), Customer.is_active.is_(True)).first()
    if not customer:
        raise HTTPException(status_code=401, detail="Cliente não encontrado")
    return {"id": customer.id, "name": customer.name, "phone_masked": mask_phone(customer.phone_normalized or customer.phone), "phone_verified_at": customer.phone_verified_at}

@router.get("/orders")
def orders(request: Request, db: Session = Depends(get_db)):
    session = get_customer_session(request)
    tenant = resolve_tenant(request, db)
    if int(session["tenant_id"]) != int(tenant.id):
        raise HTTPException(status_code=403, detail="Tenant inválido")
    rows = db.query(Order).filter(Order.tenant_id == int(tenant.id), Order.customer_id == int(session["customer_id"])).order_by(Order.created_at.desc()).limit(100).all()
    return [{"tracking_token": o.tracking_token, "status": o.status, "total_cents": o.total_cents or o.valor_total, "created_at": o.created_at} for o in rows]
