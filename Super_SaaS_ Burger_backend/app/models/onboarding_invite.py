"""One-use owner signup invitation; raw tokens are never stored."""
from sqlalchemy import Column,DateTime,Integer,String,func
from app.core.database import Base
class OnboardingInvite(Base):
    __tablename__='onboarding_invites'
    id=Column(Integer,primary_key=True)
    token_hash=Column(String(64),nullable=False,unique=True)
    expires_at=Column(DateTime(timezone=True),nullable=False)
    consumed_at=Column(DateTime(timezone=True),nullable=True)
    created_at=Column(DateTime(timezone=True),nullable=False,server_default=func.now())
