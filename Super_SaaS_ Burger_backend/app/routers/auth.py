# app/routers/auth.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.services.auth import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterPayload(BaseModel):
    name: str = Field(..., min_length=1)
    email: EmailStr
    password: str = Field(..., min_length=6)
    business_name: str = Field(..., min_length=1)


class LoginPayload(BaseModel):
    username: EmailStr
    password: str


def _user_is_admin(user: User) -> bool:
    # compat com projetos que não possuem is_admin
    role = str(getattr(user, "role", "")).lower()
    return bool(getattr(user, "is_admin", False)) or role in {"admin", "owner"}


@router.post("/register", status_code=201)
def register(payload: RegisterPayload, db: Session = Depends(get_db)):
    # email único
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")

    # cria tenant
    tenant = Tenant(business_name=payload.business_name)
    db.add(tenant)
    db.flush()  # gera tenant.id

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        tenant_id=tenant.id,
        role="owner",
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
        "tenant_id": user.tenant_id,
        "role": getattr(user, "role", None),
    }


@router.post("/login")
def login(payload: LoginPayload, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    token = create_access_token(
        str(user.id),
        extra={
            "tenant_id": int(getattr(user, "tenant_id", 0) or 0),
            "is_admin": _user_is_admin(user),
        },
    )
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login_json")
def login_json(payload: LoginPayload, db: Session = Depends(get_db)):
    # endpoint extra (mantido por compatibilidade com o seu fluxo)
    return login(payload, db)


@router.post("/token")
def token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Endpoint usado pelo botão Authorize do Swagger UI.

    Ele manda form-data com campos: username e password.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        str(user.id),
        extra={
            "tenant_id": int(getattr(user, "tenant_id", 0) or 0),
            "is_admin": _user_is_admin(user),
        },
    )
    return {"access_token": token, "token_type": "bearer"}
