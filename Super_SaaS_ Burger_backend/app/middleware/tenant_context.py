from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import SessionLocal
from app.services.tenant_resolver import TenantResolver


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.tenant = None

        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
        subdomain = TenantResolver.extract_subdomain(host)
        if subdomain:
            db = SessionLocal()
            try:
                request.state.tenant = TenantResolver.resolve_from_host(db, host)
            finally:
                db.close()

        return await call_next(request)
