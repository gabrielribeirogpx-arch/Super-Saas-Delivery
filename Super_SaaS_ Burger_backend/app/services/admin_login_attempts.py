from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.admin_login_attempt import AdminLoginAttempt

MAX_FAILED_ATTEMPTS = 8
ATTEMPT_WINDOW = timedelta(minutes=10)
LOCK_DURATION = timedelta(minutes=10)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_login_attempt(db: Session, tenant_id: int, email: str) -> Optional[AdminLoginAttempt]:
    return (
        db.query(AdminLoginAttempt)
        .filter(
            AdminLoginAttempt.tenant_id == tenant_id,
            AdminLoginAttempt.email == email,
        )
        .first()
    )


def is_locked(attempt: AdminLoginAttempt, now: Optional[datetime] = None) -> bool:
    now = now or _now()
    if attempt.locked_until is None:
        return False
    return attempt.locked_until > now


def check_login_lock(
    db: Session, tenant_id: int, email: str
) -> Tuple[bool, Optional[datetime], Optional[AdminLoginAttempt]]:
    attempt = get_login_attempt(db, tenant_id, email)
    if not attempt:
        return False, None, None
    if is_locked(attempt):
        return True, attempt.locked_until, attempt
    return False, None, attempt


def register_failed_login(
    db: Session, tenant_id: int, email: str
) -> Tuple[AdminLoginAttempt, bool]:
    now = _now()
    attempt = get_login_attempt(db, tenant_id, email)
    if attempt is None:
        attempt = AdminLoginAttempt(
            tenant_id=tenant_id,
            email=email,
            failed_count=1,
            first_failed_at=now,
            last_failed_at=now,
        )
        db.add(attempt)
    else:
        if attempt.first_failed_at is None or (now - attempt.first_failed_at) > ATTEMPT_WINDOW:
            attempt.failed_count = 0
            attempt.first_failed_at = now
        attempt.failed_count += 1
        attempt.last_failed_at = now

    locked = False
    if attempt.failed_count >= MAX_FAILED_ATTEMPTS:
        attempt.locked_until = now + LOCK_DURATION
        locked = True

    return attempt, locked


def clear_login_attempts(db: Session, tenant_id: int, email: str) -> None:
    attempt = get_login_attempt(db, tenant_id, email)
    if attempt is None:
        return
    db.delete(attempt)
