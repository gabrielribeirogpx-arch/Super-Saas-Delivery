import sqlalchemy as sa

from app.core.database import Base


class IFoodDriverDelivery(Base):
    __tablename__ = "ifood_driver_deliveries"

    id = sa.Column(sa.Integer, primary_key=True)
    order_id = sa.Column(sa.String(36), sa.ForeignKey("ifood_orders.order_id"), nullable=False, unique=True)
    assigned_driver_id = sa.Column(sa.Integer, sa.ForeignKey("admin_users.id"))
    destination = sa.Column(sa.JSON, nullable=False)
    started_at = sa.Column(sa.DateTime(timezone=True))
    completed_at = sa.Column(sa.DateTime(timezone=True))
    last_location = sa.Column(sa.JSON)
