from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import jwt

from app.core.config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET_KEY
from app.services.passwords import hash_password, verify_password

# =========================
# JWT CONFIG
# =========================
JWT_ALG = JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = JWT_EXPIRE_MINUTES


def _require_jwt_secret() -> str:
    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY não configurado.")
    return JWT_SECRET_KEY


# =========================
# JWT HELPERS
# =========================
def create_access_token(
    user_id: str,
    extra: Optional[Dict[str, Any]] = None,
    expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES,
) -> str:
    """
    IMPORTANTE:
    - "sub" precisa ser STRING (senão dá 'Subject must be a string')
    - também colocamos "user_id" por compatibilidade com deps.py
    """
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=expires_minutes)

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "user_id": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if extra:
        payload.update(extra)

    return jwt.encode(payload, _require_jwt_secret(), algorithm=JWT_ALG)


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, _require_jwt_secret(), algorithms=[JWT_ALG])


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Retorna o payload do JWT ou levanta ValueError se inválido.
    """
    try:
        return decode_token(token)
    except Exception as e:
        raise ValueError("Token inválido ou expirado") from e
