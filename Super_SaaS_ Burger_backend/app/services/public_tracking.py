from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets

TRACKING_TOKEN_TTL_DAYS = 7


def generate_tracking_token() -> str:
    return secrets.token_urlsafe(32)


def normalize_tracking_token(raw_token: str) -> str:
    token = str(raw_token or '').strip()
    if not token:
        raise ValueError('tracking token required')
    return token


def default_tracking_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=TRACKING_TOKEN_TTL_DAYS)


def is_tracking_token_active(*, tracking_expires_at: datetime | None, tracking_revoked: bool, now: datetime | None = None) -> bool:
    if tracking_revoked:
        return False

    if tracking_expires_at is None:
        return False

    now_utc = now or datetime.now(timezone.utc)
    return tracking_expires_at >= now_utc
