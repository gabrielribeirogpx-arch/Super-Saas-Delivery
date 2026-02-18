from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware

from app.services.admin_auth import ADMIN_SESSION_COOKIE, decode_admin_session


class AdminSessionMiddleware(BaseHTTPMiddleware):
    """Centralized admin session decoding from HTTP-only cookie."""

    async def dispatch(self, request, call_next):
        request.state.admin_session_payload = None

        if request.url.path.startswith('/api/admin') or request.url.path.startswith('/admin'):
            token = request.cookies.get(ADMIN_SESSION_COOKIE)
            if token:
                request.state.admin_session_payload = decode_admin_session(token)

        return await call_next(request)
