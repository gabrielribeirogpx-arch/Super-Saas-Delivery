from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import SessionLocal
from app.models.tenant import Tenant
from app.services.admin_auth import ADMIN_SESSION_COOKIE, decode_admin_session
from app.services.tenant_resolver import TenantResolutionError, TenantResolver


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.tenant = None

        db = SessionLocal()
        try:
            try:
                subdomain = TenantResolver.extract_subdomain_from_request(request)
            except TenantResolutionError:
                subdomain = None

            if subdomain:
                request.state.tenant = TenantResolver.resolve_from_subdomain(db, subdomain)
            else:
                token = request.cookies.get(ADMIN_SESSION_COOKIE)
                if token:
                    payload = decode_admin_session(token)
                    tenant_id_from_cookie = payload.get("tenant_id") if payload else None
                    if tenant_id_from_cookie is not None:
                        request.state.tenant = (
                            db.query(Tenant).filter(Tenant.id == int(tenant_id_from_cookie)).first()
                        )

                tenant_id = TenantResolver.resolve_tenant_id_from_request(request)
                if request.state.tenant is None and tenant_id is not None:
                    request.state.tenant = db.query(Tenant).filter(Tenant.id == int(tenant_id)).first()
        finally:
            db.close()

        return await call_next(request)
