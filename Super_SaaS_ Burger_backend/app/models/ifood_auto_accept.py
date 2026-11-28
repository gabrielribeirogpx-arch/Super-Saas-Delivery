import sqlalchemy as sa

from app.core.database import Base


class IFoodAutoAccept(Base):
    __tablename__ = "ifood_auto_accept"

    tenant_id = sa.Column(sa.Integer, sa.ForeignKey("tenants.id"), primary_key=True)
    merchant_id = sa.Column(sa.String(36), primary_key=True)
    enabled_at = sa.Column(sa.DateTime(timezone=True))
