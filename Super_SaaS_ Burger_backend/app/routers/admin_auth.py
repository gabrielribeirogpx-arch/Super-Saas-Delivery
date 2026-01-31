from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import (
    ADMIN_SESSION_COOKIE_SECURE,
    ADMIN_SESSION_MAX_AGE_SECONDS,
    COOKIE_DOMAIN,
)
from app.core.database import get_db
from app.deps import get_current_admin_user
from app.models.admin_user import AdminUser
from app.services.admin_audit import log_admin_action
from app.services.admin_auth import ADMIN_SESSION_COOKIE, create_admin_session
from app.services.admin_login_attempts import (
    check_login_lock,
    clear_login_attempts,
    register_failed_login,
)
from app.services.passwords import verify_password

router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])
logger = logging.getLogger(__name__)


class AdminLoginPayload(BaseModel):
    tenant_id: int = Field(..., ge=1)
    email: EmailStr
    password: str = Field(..., min_length=1)


class AdminUserRead(BaseModel):
    id: int
    tenant_id: int
    email: EmailStr
    name: str
    role: str
    active: bool


class AdminLoginResponse(AdminUserRead):
    access_token: str
    token_type: str


def _cookie_secure(request: Request | None) -> bool:
    if request and request.url.scheme == "https":
        return True
    return ADMIN_SESSION_COOKIE_SECURE


def _cookie_domain() -> str | None:
    return COOKIE_DOMAIN or None


@router.post("/login", response_model=AdminLoginResponse)
def admin_login(
    payload: AdminLoginPayload,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    locked, _, _ = check_login_lock(db, payload.tenant_id, payload.email)
    if locked:
        user = (
            db.query(AdminUser)
            .filter(
                AdminUser.tenant_id == payload.tenant_id,
                AdminUser.email == payload.email,
            )
            .first()
        )
        log_admin_action(
            db,
            tenant_id=payload.tenant_id,
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

    user = (
        db.query(AdminUser)
        .filter(
            AdminUser.tenant_id == payload.tenant_id,
            AdminUser.email == payload.email,
        )
        .first()
    )
    if not user or not user.active or not verify_password(payload.password, user.password_hash):
        _, locked_after = register_failed_login(db, payload.tenant_id, payload.email)
        log_admin_action(
            db,
            tenant_id=payload.tenant_id,
            user_id=user.id if user else 0,
            action="login_failed",
            entity_type="admin_user",
            entity_id=user.id if user else None,
            meta={"email": payload.email},
        )
        if locked_after:
            log_admin_action(
                db,
                tenant_id=payload.tenant_id,
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
    cookie_domain = _cookie_domain()
    cookie_samesite = "lax"
    cookie_secure = _cookie_secure(request)
    logger.info(
        "[AUTH_COOKIE] setting admin_session domain=%s samesite=%s secure=%s",
        cookie_domain or "host-only",
        cookie_samesite,
        cookie_secure,
    )
    cookie_kwargs: dict[str, object] = {}
    if cookie_domain:
        cookie_kwargs["domain"] = cookie_domain
    response.set_cookie(
        ADMIN_SESSION_COOKIE,
        token,
        httponly=True,
        samesite=cookie_samesite,
        path="/",
        max_age=ADMIN_SESSION_MAX_AGE_SECONDS,
        secure=cookie_secure,
        **cookie_kwargs,
    )

    clear_login_attempts(db, payload.tenant_id, payload.email)
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
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/logout")
def admin_logout(response: Response, request: Request):
    cookie_domain = _cookie_domain()
    cookie_samesite = "lax"
    cookie_secure = _cookie_secure(request)
    logger.info(
        "[AUTH_COOKIE] clearing admin_session domain=%s samesite=%s secure=%s",
        cookie_domain or "host-only",
        cookie_samesite,
        cookie_secure,
    )
    cookie_kwargs: dict[str, object] = {}
    if cookie_domain:
        cookie_kwargs["domain"] = cookie_domain
    response.delete_cookie(
        ADMIN_SESSION_COOKIE,
        samesite=cookie_samesite,
        path="/",
        secure=cookie_secure,
        **cookie_kwargs,
    )
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
