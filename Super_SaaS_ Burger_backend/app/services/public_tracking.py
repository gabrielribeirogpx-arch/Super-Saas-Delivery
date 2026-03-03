from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

TRACKING_TOKEN_TTL_DAYS = 7


def generate_tracking_token() -> str:
    return str(uuid.uuid4())


def default_tracking_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=TRACKING_TOKEN_TTL_DAYS)


def is_tracking_token_active(*, tracking_expires_at: datetime | None, tracking_revoked: bool, now: datetime | None = None) -> bool:
    if tracking_revoked:
        return False

    if tracking_expires_at is None:
        return False

    now_utc = now or datetime.now(timezone.utc)
    return tracking_expires_at >= now_utc
