from __future__ import annotations

import logging
from typing import Iterable

from fastapi import HTTPException, Request, status

from app.models.admin_user import AdminUser

logger = logging.getLogger(__name__)


class AuthorizationService:
    """Centralize tenant-scope and RBAC checks for admin endpoints."""

    @staticmethod
    def normalize_role(role: str | None) -> str:
        return (role or "").strip().lower()

    @staticmethod
    def log_access_denied(*, reason: str, user: AdminUser, tenant_id: int | None, request: Request) -> None:
        endpoint = f"{request.method} {request.url.path}"
        logger.warning(
            "Access denied (%s): user_id=%s user_role=%s user_tenant=%s tenant_id=%s endpoint=%s",
            reason,
            getattr(user, "id", None),
            getattr(user, "role", None),
            getattr(user, "tenant_id", None),
            tenant_id,
            endpoint,
        )

    @classmethod
    def ensure_tenant_access(cls, *, request: Request, user: AdminUser, tenant_id: int | None) -> int | None:
        if tenant_id is None:
            return None
        if int(user.tenant_id) != int(tenant_id):
            cls.log_access_denied(
                reason="tenant_mismatch",
                user=user,
                tenant_id=tenant_id,
                request=request,
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant não autorizado")
        return tenant_id

    @classmethod
    def ensure_role(
        cls,
        *,
        request: Request,
        user: AdminUser,
        tenant_id: int | None,
        roles: Iterable[str],
    ) -> None:
        allowed = {role.strip().lower() for role in roles}
        if "admin" in allowed or "owner" in allowed:
            allowed.update({"admin", "owner"})

        cls.ensure_tenant_access(request=request, user=user, tenant_id=tenant_id)
        if cls.normalize_role(user.role) not in allowed:
            cls.log_access_denied(
                reason="role_denied",
                user=user,
                tenant_id=tenant_id,
                request=request,
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissão insuficiente")
