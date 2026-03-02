from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import RedirectResponse

from app.services.auth import decode_access_token


class DeliveryRedirectMiddleware(BaseHTTPMiddleware):
    """Redireciona DELIVERY para /delivery ao acessar área administrativa."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/admin"):
            auth_header = request.headers.get("authorization", "")
            if auth_header.lower().startswith("bearer "):
                token = auth_header.split(" ", 1)[1].strip()
                try:
                    payload = decode_access_token(token)
                    role = str(payload.get("role", "") or "").upper()
                    if role == "DELIVERY":
                        return RedirectResponse(url="/delivery", status_code=307)
                except Exception:
                    pass

        return await call_next(request)
