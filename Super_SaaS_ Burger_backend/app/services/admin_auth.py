from __future__ import annotations

import time
from typing import Any, Dict, Optional

from fastapi import Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import (
    ADMIN_SESSION_COOKIE_DOMAIN,
    ADMIN_SESSION_COOKIE_DOMAIN_SOURCE,
    ADMIN_SESSION_COOKIE_HTTPONLY,
    ADMIN_SESSION_COOKIE_SAMESITE,
    ADMIN_SESSION_COOKIE_SECURE,
    ADMIN_SESSION_MAX_AGE_SECONDS,
    ADMIN_SESSION_SECRET,
    PUBLIC_BASE_DOMAIN,
)

ADMIN_SESSION_COOKIE = "admin_session"
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


def _cookie_secure(request: Request | None) -> bool:
    if request and request.url.scheme == "https":
        return True
    return ADMIN_SESSION_COOKIE_SECURE


def _normalize_host(host: str | None) -> str:
    value = (host or "").strip().lower()
    if not value:
        return ""
    return value.split(":")[0]


def _host_uses_platform_domain(host: str) -> bool:
    if not host or not PUBLIC_BASE_DOMAIN:
        return False
    return host == PUBLIC_BASE_DOMAIN or host.endswith(f".{PUBLIC_BASE_DOMAIN}")


def _cookie_domain(request: Request | None = None) -> str | None:
    if not ADMIN_SESSION_COOKIE_DOMAIN:
        return None

    if ADMIN_SESSION_COOKIE_DOMAIN_SOURCE == "env":
        return ADMIN_SESSION_COOKIE_DOMAIN

    host = _normalize_host(request.headers.get("x-forwarded-host") if request else None)
    if not host and request:
        host = _normalize_host(request.headers.get("host"))

    if host and not _host_uses_platform_domain(host):
        return None

    return ADMIN_SESSION_COOKIE_DOMAIN


def _cookie_samesite(secure: bool) -> str:
    if secure and ADMIN_SESSION_COOKIE_SAMESITE == "none":
        return "none"
    if not secure and ADMIN_SESSION_COOKIE_SAMESITE == "none":
        return "lax"
    return ADMIN_SESSION_COOKIE_SAMESITE


def build_admin_session_cookie_options(request: Request | None = None) -> dict[str, Any]:
    secure = _cookie_secure(request)
    options: dict[str, Any] = {
        "httponly": ADMIN_SESSION_COOKIE_HTTPONLY,
        "samesite": _cookie_samesite(secure),
        "path": "/",
        "secure": secure,
    }
    domain = _cookie_domain(request)
    if domain:
        options["domain"] = domain
    return options


def set_admin_session_cookie(response: Response, token: str, request: Request | None = None) -> None:
    response.set_cookie(
        ADMIN_SESSION_COOKIE,
        token,
        max_age=ADMIN_SESSION_MAX_AGE_SECONDS,
        **build_admin_session_cookie_options(request),
    )


def clear_admin_session_cookie(response: Response, request: Request | None = None) -> None:
    response.delete_cookie(
        ADMIN_SESSION_COOKIE,
        **build_admin_session_cookie_options(request),
    )
