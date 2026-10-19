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
    db.add(OnboardingInvite(token_hash=hashlib.sha256(raw.encode()).hexdigest(),expires_at=now+timedelta(days=7)))
    db.flush()
    return raw


def consume_invite(db,raw,*,now=None):
    if not isinstance(raw,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',raw):
        raise HTTPException(401,'Convite inválido ou expirado. Solicite um novo convite ao Fomizero.')
    now=now or datetime.now(timezone.utc)
    # UPDATE and tenant creation share the caller's transaction. Failed signup restores the invitation.
    result=db.execute(update(OnboardingInvite).where(
        OnboardingInvite.token_hash==hashlib.sha256(raw.encode()).hexdigest(),
        OnboardingInvite.expires_at>now,OnboardingInvite.consumed_at.is_(None)).values(consumed_at=now))
    if result.rowcount!=1:
        raise HTTPException(401,'Convite inválido ou expirado. Solicite um novo convite ao Fomizero.')
