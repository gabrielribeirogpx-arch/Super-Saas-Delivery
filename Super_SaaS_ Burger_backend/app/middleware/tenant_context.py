from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.concurrency import run_in_threadpool

from app.core.database import SessionLocal
from app.models.tenant import Tenant
from app.services.admin_auth import ADMIN_SESSION_COOKIE, decode_admin_session
from app.services.tenant_context import get_current_tenant_id
from app.services.tenant_resolver import TenantResolver


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):

        if request.method == "OPTIONS":
            return await call_next(request)
        request.state.tenant = None
        request.state.tenant_id = None

        from app.core.kiwify_config import WEBHOOK_PATH
        from app.core.hotmart_config import WEBHOOK_PATH as HOTMART_WEBHOOK_PATH
        if request.url.path in {WEBHOOK_PATH, HOTMART_WEBHOOK_PATH}:
            return await call_next(request)

        await run_in_threadpool(self._resolve_context, request)
        return await call_next(request)

    def _resolve_context(self, request):
        # Keep session creation, queries and close in the same worker thread.
        # Waiting for the synchronous pool must never block the event loop.
        db = SessionLocal()
        try:
            request.state.tenant = TenantResolver.resolve_tenant_from_request(db, request)

            tenant_slug = (request.query_params.get("tenant") or "").strip()
            if request.state.tenant is None and tenant_slug:
                request.state.tenant = db.query(Tenant).filter(Tenant.slug == tenant_slug).first()

            if request.state.tenant is None:
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

            request.state.tenant_id = get_current_tenant_id(request)
        finally:
            db.close()

