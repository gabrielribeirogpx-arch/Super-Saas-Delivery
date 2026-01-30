from __future__ import annotations

import time
from typing import Any, Dict, Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import ADMIN_SESSION_MAX_AGE_SECONDS, ADMIN_SESSION_SECRET

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
