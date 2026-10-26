from __future__ import annotations

import hashlib
import hmac
import os
from typing import Optional

from passlib.context import CryptContext

PBKDF2_PREFIX = "pbkdf2$"
PBKDF2_ITERATIONS = 120_000
PBKDF2_SALT_BYTES = 16

_pwd_context: Optional[CryptContext]

try:
    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except Exception:
    _pwd_context = None


def _pbkdf2_hash(password: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def hash_password(password: str) -> str:
    if _pwd_context is not None:
        try:
            return _pwd_context.hash(password)
        except Exception:
            pass

    salt = os.urandom(PBKDF2_SALT_BYTES)
    digest = _pbkdf2_hash(password, salt)
    return f"{PBKDF2_PREFIX}{PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False

    if password_hash.startswith(PBKDF2_PREFIX):
        try:
            _, iter_str, salt_hex, digest_hex = password_hash.split("$", 3)
            iterations = int(iter_str)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
        except Exception:
            return False
        computed = _pbkdf2_hash(password, salt, iterations=iterations)
        return hmac.compare_digest(computed, expected)

    if _pwd_context is None:
        return False

    try:
        return _pwd_context.verify(password, password_hash)
    except Exception:
        return False
