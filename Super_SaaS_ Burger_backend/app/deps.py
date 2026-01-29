# app/deps.py
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.admin_user import AdminUser
from app.models.user import User
from app.services.auth import decode_access_token
from app.services.admin_auth import ADMIN_SESSION_COOKIE, decode_admin_session

# Swagger "Authorize" (OAuth2 password flow) vai chamar este endpoint:
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def _extract_user_id(payload: Dict[str, Any]) -> Optional[int]:
    """Extrai o user_id do payload do JWT.

    Aceita:
    - sub (padrão JWT) como string/int
    - user_id como string/int (compatibilidade)
    """
    raw = payload.get("sub", None)
    if raw is None:
        raw = payload.get("user_id", None)

    if raw is None:
        return None

    # Se vier como int, ok
    if isinstance(raw, int):
        return raw

    # Se vier como string numérica
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.isdigit():
            return int(raw)

    return None


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Lê o JWT, valida e retorna o usuário do banco."""
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = _extract_user_id(payload)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido (sem user_id)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_tenant_access(tenant_id: int, user: User = Depends(get_current_user)) -> User:
    """Garante que o usuário pertence ao tenant da rota.

    Admin pode acessar tudo. Usuário comum apenas o próprio tenant.
    """
    # Alguns projetos não tem is_admin; use getattr de forma segura.
    is_admin = bool(getattr(user, "is_admin", False)) or (str(getattr(user, "role", "")).lower() in {"admin", "owner"})
    user_tenant_id = getattr(user, "tenant_id", None)

    if is_admin:
        return user

    if user_tenant_id is None or int(user_tenant_id) != int(tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para este tenant",
        )
    return user


def _normalize_admin_role(role: str | None) -> str:
    return (role or "").strip().lower()


def get_current_admin_user(
    request: Request,
    db: Session = Depends(get_db),
) -> AdminUser:
    token = request.cookies.get(ADMIN_SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin não autenticado")

    payload = decode_admin_session(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão expirada")

    user_id = payload.get("user_id")
    tenant_id = payload.get("tenant_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida")

    user = (
        db.query(AdminUser)
        .filter(AdminUser.id == int(user_id), AdminUser.active.is_(True))
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin não encontrado")

    if tenant_id is not None and int(user.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida")

    return user


def get_current_admin_user_ui(
    request: Request,
    db: Session = Depends(get_db),
) -> AdminUser:
    try:
        return get_current_admin_user(request, db)
    except HTTPException as exc:
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"}) from exc


def require_role(roles: Iterable[str]):
    allowed = {role.strip().lower() for role in roles}

    def _dependency(
        tenant_id: int | None = None,
        user: AdminUser = Depends(get_current_admin_user),
    ) -> AdminUser:
        if tenant_id is not None and int(user.tenant_id) != int(tenant_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant não autorizado")
        if _normalize_admin_role(user.role) not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão insuficiente")
        return user

    return _dependency


def require_role_ui(roles: Iterable[str]):
    allowed = {role.strip().lower() for role in roles}

    def _dependency(
        tenant_id: int | None = None,
        user: AdminUser = Depends(get_current_admin_user_ui),
    ) -> AdminUser:
        if tenant_id is not None and int(user.tenant_id) != int(tenant_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant não autorizado")
        if _normalize_admin_role(user.role) not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão insuficiente")
        return user

    return _dependency
