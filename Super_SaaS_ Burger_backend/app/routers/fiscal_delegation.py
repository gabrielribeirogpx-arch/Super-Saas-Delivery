"""Temporary access limited to one store's fiscal setup."""

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.admin_user import AdminUser
from app.models.fiscal_profile import FiscalProfile
from app.routers.admin_focus import (
    FiscalTestOrder, connect_tenant, fiscal_admin, focus_settings, link_tenant, settings, test_order,
)

admin_router = APIRouter(prefix="/api/admin/store/fiscal/delegation", tags=["admin-fiscal"])
access_router = APIRouter(prefix="/api/fiscal-delegation", tags=["fiscal-delegation"])


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def delegated_profile(
    x_fiscal_access: str = Header(default=""),
    db: Session = Depends(get_db),
) -> FiscalProfile:
    if re.fullmatch(r"[A-Za-z0-9_-]{43}", x_fiscal_access):
        profile = db.query(FiscalProfile).filter(
            FiscalProfile.delegate_digest == digest(x_fiscal_access),
            FiscalProfile.delegate_expires_at > datetime.now(timezone.utc),
        ).one_or_none()
        if profile:
            return profile
    raise HTTPException(401, "O acesso fiscal expirou ou foi revogado.", headers={"Cache-Control": "no-store"})


@admin_router.post("")
def issue_invite(
    response: Response,
    user: AdminUser = Depends(fiscal_admin),
    db: Session = Depends(get_db),
):
    profile = db.query(FiscalProfile).filter_by(tenant_id=user.tenant_id).with_for_update().one_or_none()
    if not profile:
        raise HTTPException(409, "Salve os dados fiscais da loja primeiro.")
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
    profile.delegate_digest = digest(token)
    profile.delegate_expires_at = expires_at
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"token": token, "expires_at": expires_at}


@admin_router.delete("", status_code=204)
def revoke_invite(
    user: AdminUser = Depends(fiscal_admin),
    db: Session = Depends(get_db),
):
    profile = db.query(FiscalProfile).filter_by(tenant_id=user.tenant_id).with_for_update().one_or_none()
    if profile:
        profile.delegate_digest = None
        profile.delegate_expires_at = None
        db.commit()


@access_router.get("")
def status(
    response: Response,
    profile: FiscalProfile = Depends(delegated_profile),
):
    response.headers["Cache-Control"] = "no-store"
    return {
        "cnpj": profile.cnpj,
        "legal_name": profile.legal_name,
        "available": settings() is not None,
        "connected": bool(profile.focus_company_id),
    }


@access_router.post("/connect")
async def connect(
    request: Request,
    profile: FiscalProfile = Depends(delegated_profile),
    db: Session = Depends(get_db),
    config: tuple[str, str] = Depends(focus_settings),
):
    return await connect_tenant(request, db, profile.tenant_id, config[0])


@access_router.post("/link")
async def link(
    request: Request,
    profile: FiscalProfile = Depends(delegated_profile),
    db: Session = Depends(get_db),
    config: tuple[str, str] = Depends(focus_settings),
):
    return await link_tenant(request, db, profile.tenant_id, config[0])


@access_router.post("/test")
def emit_test(
    data: FiscalTestOrder,
    profile: FiscalProfile = Depends(delegated_profile),
    db: Session = Depends(get_db),
    config: tuple[str, str] = Depends(focus_settings),
):
    return test_order(db, profile.tenant_id, data, config)
