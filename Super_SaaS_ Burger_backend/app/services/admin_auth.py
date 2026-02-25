from __future__ import annotations

import time
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from fastapi import Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import (
    ADMIN_SESSION_MAX_AGE_SECONDS,
    ADMIN_SESSION_SECRET,
    ADMIN_SESSION_COOKIE_DOMAIN,
    ADMIN_SESSION_COOKIE_HTTPONLY,
    ADMIN_SESSION_COOKIE_SAMESITE,
    ADMIN_SESSION_COOKIE_SECURE,
)

ADMIN_SESSION_COOKIE = "admin_session"
ADMIN_SESSION_COOKIE_NAME = ADMIN_SESSION_COOKIE
ADMIN_SESSION_SALT = "admin-session"


def _serializer() -> URLSafeTimedSerializer:
    if not ADMIN_SESSION_SECRET:
        raise RuntimeError("ADMIN_SESSION_SECRET não configurado.")
    return URLSafeTimedSerializer(ADMIN_SESSION_SECRET, salt=ADMIN_SESSION_SALT)


def create_admin_session(payload: Dict[str, Any]) -> str:
    if "exp" not in payload:
        payload = {
            **payload,
            "exp": int(time.time()) + ADMIN_SESSION_MAX_AGE_SECONDS,
        }
    return _serializer().dumps(payload)


def decode_admin_session(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = _serializer().loads(token, max_age=ADMIN_SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired, ValueError):
        return None
    exp = payload.get("exp")
    if exp is not None:
        try:
            if int(exp) < int(time.time()):
                return None
        except (TypeError, ValueError):
            return None
    return payload


def build_admin_session_cookie_options(request: Request | None = None) -> dict[str, Any]:
    secure = ADMIN_SESSION_COOKIE_SECURE
    samesite = ADMIN_SESSION_COOKIE_SAMESITE

    host = ""
    origin_host = ""
    if request is not None:
        host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").lower()
        host = host.split(",")[0].strip().split(":")[0]

        origin = (request.headers.get("origin") or "").strip()
        if origin:
            origin_host = (urlsplit(origin).hostname or "").lower()

    is_local_request = host in {"", "localhost", "127.0.0.1"}
    is_cross_site_request = bool(origin_host and host and origin_host != host)

    # Segurança defensiva: em hosts públicos, nunca emitir cookie inseguro.
    if not is_local_request:
        secure = True

    # Login via frontend->API em domínios distintos exige SameSite=None.
    if is_cross_site_request and secure:
        samesite = "none"

    # Browsers rejeitam SameSite=None sem Secure.
    if samesite == "none" and not secure:
        samesite = "lax"

    return {
        "domain": ADMIN_SESSION_COOKIE_DOMAIN,
        "httponly": ADMIN_SESSION_COOKIE_HTTPONLY,
        "samesite": samesite,
        "path": "/",
        "secure": secure,
    }


def set_admin_session_cookie(response: Response, token: str, request: Request | None = None) -> None:
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE_NAME,
        value=token,
        max_age=ADMIN_SESSION_MAX_AGE_SECONDS,
        **build_admin_session_cookie_options(request),
    )


def clear_admin_session_cookie(response: Response, request: Request | None = None) -> None:
    response.delete_cookie(
        key=ADMIN_SESSION_COOKIE_NAME,
        **build_admin_session_cookie_options(request),
    )
