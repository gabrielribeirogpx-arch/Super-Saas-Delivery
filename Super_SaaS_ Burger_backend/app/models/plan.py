from sqlalchemy import Boolean, Column, DateTime, Integer, String, UniqueConstraint, func

from app.core.database import Base


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (UniqueConstraint("code", name="uq_plans_code"),)

    id = Column(Integer, primary_key=True)
    code = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
