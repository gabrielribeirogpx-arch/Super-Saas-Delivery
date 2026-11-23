"""Verification of short-lived customer identity claims signed by Wazza."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import json
import re
import time
from typing import Any

from app.models.wazza_mcp import WazzaMcpCredential


CONTEXT_HEADER = "X-Wazza-Customer-Context"
SIGNATURE_HEADER = "X-Wazza-Customer-Signature"
MAX_CONTEXT_TTL_SECONDS = 90
CLOCK_SKEW_SECONDS = 15
_PHONE_PATTERN = re.compile(r"^[0-9]{8,15}$")
_ALLOWED_CLAIMS = {"aud", "cid", "exp", "iat", "iss", "rid", "sub", "v"}


class WazzaMcpIdentityError(ValueError):
    pass


@dataclass(frozen=True)
class VerifiedCustomerIdentity:
    phone: str
    conversation_id: str | None
    issued_at: int
    expires_at: int


def _decode_base64url(value: str) -> bytes:
    if not value or len(value) > 2048 or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise WazzaMcpIdentityError("invalid_customer_context")
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, TypeError) as exc:
        raise WazzaMcpIdentityError("invalid_customer_context") from exc


def verify_customer_identity(
    *,
    credential: WazzaMcpCredential,
    encoded_context: str | None,
    encoded_signature: str | None,
    request_id: str,
    now: int | None = None,
) -> VerifiedCustomerIdentity | None:
    if not encoded_context and not encoded_signature:
        return None
    if not encoded_context or not encoded_signature:
        raise WazzaMcpIdentityError("incomplete_customer_context")

    try:
        signing_key = bytes.fromhex(str(credential.token_hash))
    except ValueError as exc:
        raise WazzaMcpIdentityError("invalid_credential_key") from exc
    if len(signing_key) != hashlib.sha256().digest_size:
        raise WazzaMcpIdentityError("invalid_credential_key")
    expected = hmac.new(signing_key, encoded_context.encode("ascii"), hashlib.sha256).digest()
    supplied = _decode_base64url(encoded_signature)
    if not hmac.compare_digest(expected, supplied):
        raise WazzaMcpIdentityError("invalid_customer_signature")

    try:
        claims: Any = json.loads(_decode_base64url(encoded_context))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WazzaMcpIdentityError("invalid_customer_context") from exc
    if not isinstance(claims, dict) or set(claims) - _ALLOWED_CLAIMS:
        raise WazzaMcpIdentityError("invalid_customer_context")
    if claims.get("v") != 1 or claims.get("iss") != "wazza" or claims.get("aud") != "fomizero-mcp":
        raise WazzaMcpIdentityError("invalid_customer_context")
    if str(claims.get("rid") or "") != str(request_id):
        raise WazzaMcpIdentityError("customer_context_request_mismatch")

    phone = str(claims.get("sub") or "")
    conversation_id = str(claims.get("cid") or "") or None
    if not _PHONE_PATTERN.fullmatch(phone) or (conversation_id is not None and len(conversation_id) > 128):
        raise WazzaMcpIdentityError("invalid_customer_context")
    if isinstance(claims.get("iat"), bool) or isinstance(claims.get("exp"), bool):
        raise WazzaMcpIdentityError("invalid_customer_context")
    try:
        issued_at = int(claims["iat"])
        expires_at = int(claims["exp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WazzaMcpIdentityError("invalid_customer_context") from exc
    current = int(time.time() if now is None else now)
    if expires_at <= issued_at or expires_at - issued_at > MAX_CONTEXT_TTL_SECONDS:
        raise WazzaMcpIdentityError("invalid_customer_context_ttl")
    if issued_at > current + CLOCK_SKEW_SECONDS or expires_at < current - CLOCK_SKEW_SECONDS:
        raise WazzaMcpIdentityError("expired_customer_context")
    return VerifiedCustomerIdentity(phone, conversation_id, issued_at, expires_at)
