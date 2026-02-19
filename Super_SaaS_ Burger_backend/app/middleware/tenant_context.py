from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import SessionLocal
from app.services.tenant_resolver import TenantResolver


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.tenant = None

        subdomain = TenantResolver.extract_subdomain_from_request(request)
        if subdomain:
            db = SessionLocal()
            try:
                request.state.tenant = TenantResolver.resolve_from_subdomain(db, subdomain)
            finally:
                db.close()

        return await call_next(request)
