import sqlalchemy as sa

from app.core.database import Base


class FiscalProfile(Base):
    __tablename__ = "fiscal_profiles"
    __table_args__ = (sa.UniqueConstraint("focus_company_id", name="uq_fiscal_profiles_focus_company"),)

    tenant_id = sa.Column(sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    cnpj = sa.Column(sa.String(14), nullable=False)
    legal_name = sa.Column(sa.String(120), nullable=False)
    state_registration = sa.Column(sa.String(14), nullable=False)
    state_code = sa.Column(sa.String(2), nullable=False)
    tax_regime = sa.Column(sa.Integer, nullable=False)
    focus_company_id = sa.Column(sa.Integer, nullable=True)
    delegate_digest = sa.Column(sa.String(64), index=True, unique=True, nullable=True)
    delegate_expires_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
