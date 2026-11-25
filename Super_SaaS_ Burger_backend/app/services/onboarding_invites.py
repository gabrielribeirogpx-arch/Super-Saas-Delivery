"""Explicit operator issuance and transactional, race-safe invite redemption."""
from datetime import datetime,timedelta,timezone
import hashlib
import re
import secrets
from sqlalchemy import update
from fastapi import HTTPException
from app.models.onboarding_invite import OnboardingInvite


def issue_invite(db,*,now=None):
    now=now or datetime.now(timezone.utc)
    raw=secrets.token_urlsafe(32)
    store_signup_token(db, hashlib.sha256(raw.encode()).hexdigest(), now + timedelta(days=7))
    return raw


def consume_invite(db,raw,*,now=None):
    if not isinstance(raw,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',raw):
        raise HTTPException(401,'Convite inválido ou expirado. Solicite um novo convite ao Fomizero.')
    now=now or datetime.now(timezone.utc)
    if not redeem_signup_token(db, hashlib.sha256(raw.encode()).hexdigest(), now):
        raise HTTPException(401,'Convite inválido ou expirado. Solicite um novo convite ao Fomizero.')

def store_signup_token(db, digest, expires_at):
    db.add(OnboardingInvite(token_hash=digest, expires_at=expires_at))
    db.flush()


def redeem_signup_token(db, digest, now):
    # Redemption shares the account creation transaction, including rollback.
    result = db.execute(update(OnboardingInvite).where(
        OnboardingInvite.token_hash == digest,
        OnboardingInvite.expires_at > now,
        OnboardingInvite.consumed_at.is_(None),
    ).values(consumed_at=now))
    return result.rowcount == 1
