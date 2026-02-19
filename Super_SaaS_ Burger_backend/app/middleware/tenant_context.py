from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.database import SessionLocal
from app.models.tenant import Tenant
from utils.slug import normalize_slug

ROOT_SUBDOMAINS = {"www", "servicedelivery", "localhost"}


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        host_header = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip().lower()
        host = host_header.split(":")[0].strip()
        subdomain = host.split(".")[0] if host else ""

        if subdomain in ROOT_SUBDOMAINS or host in {"", "servicedelivery.com.br"}:
            request.state.tenant = None
            return await call_next(request)

        slug = normalize_slug(subdomain)
        if not slug:
            return JSONResponse(status_code=404, content={"detail": "Tenant não encontrado"})

        session_factory = getattr(request.app.state, "session_factory", SessionLocal)
        db = session_factory()
        try:
            tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
        finally:
            db.close()

        if not tenant:
            return JSONResponse(status_code=404, content={"detail": "Tenant não encontrado"})

        request.state.tenant = tenant
        return await call_next(request)
