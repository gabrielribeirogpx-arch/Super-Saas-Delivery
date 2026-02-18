from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.metrics import request_metrics
from app.core.request_context import clear_request_context, set_request_context

logger = logging.getLogger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        set_request_context(request_id=request_id)

        status_code = 500
        endpoint = request.url.path
        method = request.method

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            tenant_id = _extract_tenant_id(request)
            user_id = _extract_user_id(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)

            set_request_context(tenant_id=tenant_id, user_id=user_id)
            request_metrics.observe(endpoint=endpoint, method=method, status_code=status_code, duration_ms=duration_ms)

            logger.info(
                "request completed",
                extra={
                    "request_id": request_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "endpoint": endpoint,
                    "method": method,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )

            if "response" in locals():
                response.headers["X-Request-ID"] = request_id

            clear_request_context()


def _extract_tenant_id(request: Request) -> str | None:
    tenant = request.path_params.get("tenant_id") or request.query_params.get("tenant_id")
    if tenant:
        return str(tenant)
    header_tenant = request.headers.get("X-Tenant-ID")
    if header_tenant:
        return header_tenant
    return None


def _extract_user_id(request: Request) -> str | None:
    user = getattr(request.state, "user", None)
    if user is None:
        return None
    user_id = getattr(user, "id", None)
    return str(user_id) if user_id is not None else None
