from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from jose import jwt


# =========================
# JWT CONFIG
# =========================
JWT_SECRET = "CHANGE_ME_SUPER_SECRET"  # depois a gente joga isso em .env
JWT_ALG = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24h


# =========================
# PASSWORD (bcrypt direto, sem passlib)
# - evita erro do passlib com bcrypt 5.x
# - evita limite de 72 bytes (faz fallback)
# =========================
def _normalize_password_for_bcrypt(password: str) -> bytes:
    """
    bcrypt só considera até 72 bytes.
    Se a senha passar disso, normalizamos para não quebrar.
    """
    pw = (password or "").encode("utf-8")
    if len(pw) <= 72:
        return pw

    # fallback simples: trunca (mantém compatível)
    # (poderia ser SHA256 antes, mas truncar já resolve o crash)
    return pw[:72]


def hash_password(password: str) -> str:
    pw = _normalize_password_for_bcrypt(password)
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pw, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        pw = _normalize_password_for_bcrypt(plain_password)
        ph = (password_hash or "").encode("utf-8")
        return bcrypt.checkpw(pw, ph)
    except Exception:
        return False


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

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Retorna o payload do JWT ou levanta ValueError se inválido.
    """
    try:
        return decode_token(token)
    except Exception as e:
        raise ValueError("Token inválido ou expirado") from e
