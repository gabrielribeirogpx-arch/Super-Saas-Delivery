import sqlalchemy as sa

from app.core.database import Base


class IFoodEvent(Base):
    __tablename__ = "ifood_events"

    event_id = sa.Column(sa.String(36), primary_key=True)
    tenant_id = sa.Column(sa.Integer, sa.ForeignKey("tenants.id"), nullable=False)
    merchant_id = sa.Column(sa.String(36), nullable=False)
    order_id = sa.Column(sa.String(36), nullable=True)
    code = sa.Column(sa.String(64), nullable=False)
    occurred_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
    received_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    __table_args__ = (
        sa.Index("ix_ifood_events_tenant_order", "tenant_id", "order_id"),
    )
