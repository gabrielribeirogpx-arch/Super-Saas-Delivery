import sqlalchemy as sa

from app.core.database import Base


class IFoodOrder(Base):
    __tablename__ = "ifood_orders"

    order_id = sa.Column(sa.String(36), primary_key=True)
    tenant_id = sa.Column(sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, index=True)
    merchant_id = sa.Column(sa.String(36), nullable=False)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
    imported_at = sa.Column(sa.DateTime(timezone=True))
    details = sa.Column(sa.JSON, nullable=False)
    confirmation_requested_at = sa.Column(sa.DateTime(timezone=True))
    ready_requested_at = sa.Column(sa.DateTime(timezone=True))
    cancellation_requested_at = sa.Column(sa.DateTime(timezone=True))
    dispatch_requested_at = sa.Column(sa.DateTime(timezone=True))
