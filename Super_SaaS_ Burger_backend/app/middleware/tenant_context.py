from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import SessionLocal
from app.models.tenant import Tenant
from app.services.tenant_resolver import TenantResolver


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.tenant = None

        db = SessionLocal()
        try:
            subdomain = TenantResolver.extract_subdomain_from_request(request)
            if subdomain:
                request.state.tenant = TenantResolver.resolve_from_subdomain(db, subdomain)
            else:
                tenant_id = TenantResolver.resolve_tenant_id_from_request(request)
                if tenant_id is not None:
                    request.state.tenant = db.query(Tenant).filter(Tenant.id == int(tenant_id)).first()
        finally:
            db.close()

        return await call_next(request)
