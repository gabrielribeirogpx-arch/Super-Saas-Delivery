"""Credential lifecycle and authorization for the Wazza MCP integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import re
import secrets
from typing import Iterable

from sqlalchemy.orm import Session

from app.core import config
from app.models.wazza_mcp import WazzaMcpCredential


TOKEN_PATTERN = re.compile(r"^fmz_mcp_([0-9a-f]{16})\.([A-Za-z0-9_-]{32,})$")
VALID_SCOPES = frozenset(
    {
        "menu:read",
        "customer:read",
        "order:read",
        "order:draft",
        "order:create",
        "order:edit",
        "order:cancel",
    }
)


class WazzaMcpAuthError(Exception):
    """Stable, non-secret error suitable for mapping to an MCP response."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class IssuedCredential:
    credential: WazzaMcpCredential
    token: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def normalize_scopes(scopes: Iterable[str]) -> list[str]:
    normalized = sorted({str(scope).strip().lower() for scope in scopes if str(scope).strip()})
    invalid = set(normalized) - VALID_SCOPES
    if invalid or not normalized:
        raise ValueError("invalid_wazza_mcp_scopes")
    return normalized


def issue_credential(
    db: Session,
    *,
    tenant_id: int,
    name: str,
    scopes: Iterable[str],
    expires_at: datetime | None = None,
    now: datetime | None = None,
) -> IssuedCredential:
    normalized_name = name.strip()
    if not normalized_name or len(normalized_name) > 120:
        raise ValueError("invalid_wazza_mcp_credential_name")
    current = now or _now()
    if expires_at is not None and _as_utc(expires_at) <= _as_utc(current):
        raise ValueError("invalid_wazza_mcp_expiry")

    key_id = secrets.token_hex(8)
    raw_token = f"fmz_mcp_{key_id}.{secrets.token_urlsafe(32)}"
    credential = WazzaMcpCredential(
        tenant_id=tenant_id,
        key_id=key_id,
        token_hash=_digest(raw_token),
        name=normalized_name,
        scopes_json=normalize_scopes(scopes),
        created_at=current,
        expires_at=expires_at,
    )
    db.add(credential)
    db.flush()
    return IssuedCredential(credential=credential, token=raw_token)


def authenticate_credential(
    db: Session,
    raw_token: str,
    *,
    enabled: bool | None = None,
    now: datetime | None = None,
) -> WazzaMcpCredential:
    if enabled is None:
        enabled = config.WAZZA_MCP_ENABLED
    if not enabled:
        raise WazzaMcpAuthError("integration_disabled")

    match = TOKEN_PATTERN.fullmatch(raw_token or "")
    if match is None:
        raise WazzaMcpAuthError("invalid_credential")
    credential = db.query(WazzaMcpCredential).filter(WazzaMcpCredential.key_id == match.group(1)).first()
    if credential is None or not hmac.compare_digest(credential.token_hash, _digest(raw_token)):
        raise WazzaMcpAuthError("invalid_credential")

    current = now or _now()
    if credential.revoked_at is not None:
        raise WazzaMcpAuthError("invalid_credential")
    if credential.expires_at is not None and _as_utc(credential.expires_at) <= _as_utc(current):
        raise WazzaMcpAuthError("invalid_credential")

    credential.last_used_at = current
    return credential


def require_scope(credential: WazzaMcpCredential, scope: str) -> None:
    if scope not in VALID_SCOPES or scope not in set(credential.scopes_json or []):
        raise WazzaMcpAuthError("insufficient_scope")


def revoke_credential(
    credential: WazzaMcpCredential,
    *,
    now: datetime | None = None,
) -> bool:
    if credential.revoked_at is not None:
        return False
    credential.revoked_at = now or _now()
    return True
