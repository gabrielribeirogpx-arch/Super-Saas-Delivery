from __future__ import annotations

import re
import unicodedata
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import IS_PROD, ONBOARDING_API_TOKEN
from app.core.database import get_db
from app.models.admin_user import AdminUser
from app.models.menu_category import MenuCategory
from app.models.menu_item import MenuItem
from app.models.tenant import Tenant
from app.models.tenant_public_settings import TenantPublicSettings
from app.services.passwords import hash_password

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

SLUG_PATTERN = re.compile(r"^[a-z0-9-]{3,}$")
DOMAIN_PATTERN = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")


class OnboardingRequest(BaseModel):
    business_name: str = Field(..., min_length=2, max_length=120)
    slug: str | None = Field(default=None, min_length=3, max_length=80)
    custom_domain: str | None = Field(default=None, max_length=255)
    admin_name: str = Field(..., min_length=2, max_length=120)
    admin_email: EmailStr
    admin_password: str = Field(..., min_length=8, max_length=200)


class AvailabilityResponse(BaseModel):
    slug: str | None = None
    slug_available: bool | None = None
    custom_domain: str | None = None
    custom_domain_available: bool | None = None


class OnboardingResponse(BaseModel):
    tenant_id: int
    slug: str
    custom_domain: str | None
    business_name: str
    admin_email: EmailStr


def _ensure_onboarding_security(x_onboarding_token: str | None) -> None:
    if not IS_PROD:
        return
    configured = (ONBOARDING_API_TOKEN or "").strip()
    incoming = (x_onboarding_token or "").strip()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Onboarding em produção requer ONBOARDING_API_TOKEN configurado",
        )
    if incoming != configured:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")


def _normalize_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug


def _normalize_custom_domain(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized == "":
        return None
    if not DOMAIN_PATTERN.match(normalized):
        raise HTTPException(status_code=400, detail="Domínio personalizado inválido")
    return normalized


def _slug_exists(db: Session, slug: str) -> bool:
    return db.query(Tenant.id).filter(Tenant.slug == slug).first() is not None


def _domain_exists(db: Session, custom_domain: str) -> bool:
    return (
        db.query(Tenant.id)
        .filter(func.lower(Tenant.custom_domain) == custom_domain)
        .first()
        is not None
    )


def _generate_unique_slug(db: Session, business_name: str, requested_slug: str | None) -> str:
    candidate = _normalize_slug(requested_slug or business_name)
    if not candidate:
        candidate = "loja"
    if len(candidate) < 3:
        candidate = f"{candidate}-loja"
    candidate = candidate[:70].strip("-")
    if not candidate:
        candidate = "loja"

    if not SLUG_PATTERN.match(candidate):
        raise HTTPException(status_code=400, detail="Slug inválido")

    if not _slug_exists(db, candidate):
        return candidate

    suffix = 2
    while suffix <= 9999:
        with_suffix = f"{candidate}-{suffix}"
        if len(with_suffix) > 80:
            with_suffix = with_suffix[:80].strip("-")
        if not _slug_exists(db, with_suffix):
            return with_suffix
        suffix += 1

    raise HTTPException(status_code=409, detail="Não foi possível gerar slug único")


def _seed_tenant_defaults(db: Session, tenant_id: int) -> None:
    category = MenuCategory(
        tenant_id=tenant_id,
        name="Mais pedidos",
        sort_order=1,
        active=True,
    )
    db.add(category)
    db.flush()

    sample_item = MenuItem(
        tenant_id=tenant_id,
        category_id=category.id,
        name="Hambúrguer da Casa",
        description="Pão brioche, hambúrguer 160g, queijo e molho especial.",
        price_cents=2990,
        active=True,
        production_area="COZINHA",
    )
    db.add(sample_item)

    business_settings = TenantPublicSettings(
        tenant_id=tenant_id,
        theme="dark",
        primary_color="#2563eb",
    )
    db.add(business_settings)


@router.get("/availability", response_model=AvailabilityResponse)
def check_slug_and_domain_availability(
    slug: str | None = None,
    custom_domain: str | None = None,
    db: Session = Depends(get_db),
):
    normalized_slug = None
    slug_available = None
    if slug is not None:
        normalized_slug = _normalize_slug(slug)
        if not SLUG_PATTERN.match(normalized_slug):
            raise HTTPException(status_code=400, detail="Slug inválido")
        slug_available = not _slug_exists(db, normalized_slug)

    normalized_domain = None
    custom_domain_available = None
    if custom_domain is not None:
        normalized_domain = _normalize_custom_domain(custom_domain)
        if normalized_domain is not None:
            custom_domain_available = not _domain_exists(db, normalized_domain)
        else:
            custom_domain_available = True

    return AvailabilityResponse(
        slug=normalized_slug,
        slug_available=slug_available,
        custom_domain=normalized_domain,
        custom_domain_available=custom_domain_available,
    )


@router.post("/tenant", response_model=OnboardingResponse, status_code=201)
def create_tenant_with_owner(
    payload: OnboardingRequest,
    x_onboarding_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _ensure_onboarding_security(x_onboarding_token)

    custom_domain = _normalize_custom_domain(payload.custom_domain)
    if custom_domain and _domain_exists(db, custom_domain):
        raise HTTPException(status_code=409, detail="Domínio personalizado já em uso")

    slug = _generate_unique_slug(db, payload.business_name, payload.slug)

    tenant = Tenant(
        business_name=payload.business_name.strip(),
        slug=slug,
        custom_domain=custom_domain,
    )
    db.add(tenant)
    db.flush()

    owner = AdminUser(
        tenant_id=tenant.id,
        email=payload.admin_email.lower().strip(),
        name=payload.admin_name.strip(),
        password_hash=hash_password(payload.admin_password),
        role="owner",
        active=True,
        created_at=datetime.utcnow(),
    )
    db.add(owner)

    _seed_tenant_defaults(db, tenant.id)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return OnboardingResponse(
        tenant_id=tenant.id,
        slug=tenant.slug,
        custom_domain=tenant.custom_domain,
        business_name=tenant.business_name,
        admin_email=owner.email,
    )
