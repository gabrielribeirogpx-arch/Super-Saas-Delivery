from __future__ import annotations

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.models.admin_user import AdminUser
from app.services.admin_auth import ADMIN_SESSION_COOKIE, decode_admin_session


class AuthService:
    """Centralized admin session authentication service (HTTP-only cookie)."""

    @staticmethod
    def authenticate_admin_session(request: Request, db: Session) -> AdminUser:
        token = request.cookies.get(ADMIN_SESSION_COOKIE)
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin não autenticado")

        payload = getattr(request.state, "admin_session_payload", None)
        if payload is None and token:
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
