import sqlalchemy as sa

from app.core.database import Base


class IFoodConnection(Base):
    __tablename__ = "ifood_connections"

    tenant_id = sa.Column(sa.Integer, sa.ForeignKey("tenants.id"), primary_key=True)
    merchant_id = sa.Column(sa.String(36), unique=True, nullable=False)
    merchant_name = sa.Column(sa.String(255), nullable=False)
    encrypted_tokens = sa.Column(sa.Text, nullable=False)
    expires_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
