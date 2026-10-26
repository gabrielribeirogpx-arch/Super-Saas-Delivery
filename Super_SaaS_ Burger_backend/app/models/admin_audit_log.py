from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, Integer, String, Text

from app.core.database import Base


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    __table_args__ = (
        CheckConstraint("(actor_type = 'user' AND user_id IS NOT NULL) OR (actor_type IN ('system', 'provider') AND user_id IS NULL)", name="ck_admin_audit_actor"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    actor_type = Column(String(20), nullable=False, default="user", server_default="user")
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=True)
    entity_id = Column(Integer, nullable=True)
    meta_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
