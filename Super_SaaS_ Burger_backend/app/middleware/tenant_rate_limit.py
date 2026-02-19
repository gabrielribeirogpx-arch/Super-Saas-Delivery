from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.rate_limiter import InMemoryRateLimiterService, RateLimiterService


class TenantRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, rate_limiter: RateLimiterService | None = None) -> None:
        super().__init__(app)
        self._rate_limiter = rate_limiter or InMemoryRateLimiterService()

    async def dispatch(self, request: Request, call_next):
        tenant_id = _extract_tenant_id(request)
        if not tenant_id:
            return await call_next(request)

        endpoint = request.url.path
        decision = self._rate_limiter.check(tenant_id=tenant_id, endpoint=endpoint)
        if not decision.allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={
                    "Retry-After": str(decision.retry_after_seconds),
                    "X-RateLimit-Limit": str(decision.limit),
                    "X-RateLimit-Remaining": str(decision.remaining),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(decision.limit)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        return response


def _extract_tenant_id(request: Request) -> str | None:
    tenant = request.path_params.get("tenant_id") or request.query_params.get("tenant_id")
    if tenant:
        return str(tenant)
    header_tenant = request.headers.get("X-Tenant-ID")
    if header_tenant:
        return header_tenant
    return None
