from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid
from sqlalchemy.orm import Session

TRACKING_TOKEN_TTL_DAYS = 7
TRACKING_TOKEN_MAX_LENGTH = 36


def generate_tracking_token() -> str:
    return str(uuid.uuid4())


def normalize_tracking_token(raw_token: str) -> str:
    token = str(raw_token or '').strip()
    if not token:
        raise ValueError('tracking token required')
    return token



def ensure_order_tracking_token(db: Session, order, *, max_attempts: int = 8) -> str:
    token = normalize_tracking_token(getattr(order, "tracking_token", "") or generate_tracking_token())

    if not hasattr(db, "query"):
        order.tracking_token = token
        return token

    from app.models.order import Order

    for _attempt in range(max_attempts):
        existing_order_id = (
            db.query(Order.id)
            .filter(Order.tracking_token == token)
            .scalar()
        )
        if existing_order_id is None or int(existing_order_id) == int(getattr(order, "id", 0) or 0):
            order.tracking_token = token
            return token
        token = generate_tracking_token()

    raise RuntimeError("unable to allocate unique tracking token")


def default_tracking_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=TRACKING_TOKEN_TTL_DAYS)


def is_tracking_token_active(*, tracking_expires_at: datetime | None, tracking_revoked: bool, now: datetime | None = None) -> bool:
    if tracking_revoked:
        return False

    if tracking_expires_at is None:
        return False

    expires_at = tracking_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    return expires_at >= now_utc
