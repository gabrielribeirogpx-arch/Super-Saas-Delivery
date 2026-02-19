from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_admin_user
from app.models.admin_user import AdminUser
from app.models.tenant import Tenant
from app.services.tenant_resolver import TenantResolver
from app.services.admin_audit import log_admin_action
from app.services.admin_auth import (
    create_admin_session,
    clear_admin_session_cookie,
    set_admin_session_cookie,
    build_admin_session_cookie_options,
)
from app.services.admin_login_attempts import (
    check_login_lock,
    clear_login_attempts,
    register_failed_login,
)
from app.services.passwords import verify_password

router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])
logger = logging.getLogger(__name__)




def resolve_tenant_from_host(db: Session, host: str):
    """Backward-compatible alias for tenant resolution."""
    return TenantResolver.resolve_from_host(db, host)


def resolve_tenant_from_slug(db: Session, slug: str):
    normalized_slug = (slug or "").strip().lower()
    if not normalized_slug:
        return None
    return db.query(Tenant).filter(Tenant.slug == normalized_slug).first()


def resolve_tenant_from_email(db: Session, email: str, password: str):
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        return None, None

    users = (
        db.query(AdminUser)
        .filter(
            AdminUser.email == normalized_email,
            AdminUser.active.is_(True),
        )
        .all()
    )
    matched_users = [user for user in users if verify_password(password, user.password_hash)]
    if len(matched_users) != 1:
        return None, None

    user = matched_users[0]
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if tenant is None:
        return None, None
    return tenant, user


class AdminLoginPayload(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class AdminUserRead(BaseModel):
    id: int
    tenant_id: int
    email: EmailStr
    name: str
    role: str
    active: bool


@router.post("/login", response_model=AdminUserRead)
def admin_login(
    payload: AdminLoginPayload,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    tenant_slug = request.headers.get("x-tenant-slug") or ""
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    tenant = resolve_tenant_from_slug(db, tenant_slug)
    preauthenticated_user = None
    if tenant is None:
        try:
            tenant = resolve_tenant_from_host(db, host)
        except HTTPException as exc:
            tenant, preauthenticated_user = resolve_tenant_from_email(db, payload.email, payload.password)
            if tenant is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Não foi possível resolver o tenant a partir do domínio. Use um subdomínio válido.",
                ) from exc

    locked, _, _ = check_login_lock(db, tenant.id, payload.email)
    if locked:
        user = (
            db.query(AdminUser)
            .filter(
                AdminUser.tenant_id == tenant.id,
                AdminUser.email == payload.email,
            )
            .first()
        )
        log_admin_action(
            db,
            tenant_id=tenant.id,
            user_id=user.id if user else 0,
            action="login_locked",
            entity_type="admin_user",
            entity_id=user.id if user else None,
            meta={"email": payload.email},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas. Tente novamente em alguns minutos.",
        )

    user = preauthenticated_user or (
        db.query(AdminUser)
        .filter(
            AdminUser.tenant_id == tenant.id,
            AdminUser.email == payload.email,
        )
        .first()
    )
    password_is_valid = preauthenticated_user is not None or (
        user is not None and verify_password(payload.password, user.password_hash)
    )
    if not user or not user.active or not password_is_valid:
        _, locked_after = register_failed_login(db, tenant.id, payload.email)
        log_admin_action(
            db,
            tenant_id=tenant.id,
            user_id=user.id if user else 0,
            action="login_failed",
            entity_type="admin_user",
            entity_id=user.id if user else None,
            meta={"email": payload.email},
        )
        if locked_after:
            log_admin_action(
                db,
                tenant_id=tenant.id,
                user_id=user.id if user else 0,
                action="login_locked",
                entity_type="admin_user",
                entity_id=user.id if user else None,
                meta={"email": payload.email},
            )
        db.commit()
        if locked_after:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas tentativas. Tente novamente em alguns minutos.",
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    token = create_admin_session(
        {"user_id": user.id, "tenant_id": user.tenant_id, "role": user.role}
    )
    cookie_options = build_admin_session_cookie_options(request)
    logger.info(
        "[AUTH_COOKIE] setting admin_session domain=%s samesite=%s secure=%s",
        cookie_options.get("domain", "host-only"),
        cookie_options["samesite"],
        cookie_options["secure"],
    )
    set_admin_session_cookie(response, token, request)

    clear_login_attempts(db, tenant.id, payload.email)
    log_admin_action(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="login_success",
    )
    db.commit()

    return {
        "id": user.id,
        "tenant_id": user.tenant_id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "active": user.active,
    }


@router.post("/logout")
def admin_logout(response: Response, request: Request):
    cookie_options = build_admin_session_cookie_options(request)
    logger.info(
        "[AUTH_COOKIE] clearing admin_session domain=%s samesite=%s secure=%s",
        cookie_options.get("domain", "host-only"),
        cookie_options["samesite"],
        cookie_options["secure"],
    )
    clear_admin_session_cookie(response, request)
    return {"ok": True}


@router.get("/me", response_model=AdminUserRead)
def admin_me(user: AdminUser = Depends(get_current_admin_user)):
    return {
        "id": user.id,
        "tenant_id": user.tenant_id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "active": user.active,
    }
