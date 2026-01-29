from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from app.core.database import Base


class AdminLoginAttempt(Base):
    __tablename__ = "admin_login_attempts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_admin_login_attempts_tenant_email"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    email = Column(String, nullable=False, index=True)
    failed_count = Column(Integer, nullable=False, default=0)
    first_failed_at = Column(DateTime, nullable=True)
    last_failed_at = Column(DateTime, nullable=True)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
