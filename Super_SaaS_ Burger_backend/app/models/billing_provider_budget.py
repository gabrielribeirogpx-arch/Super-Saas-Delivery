from sqlalchemy import Column, DateTime, String
from app.core.database import Base


class BillingProviderBudget(Base):
    """Global deployment budget survives restarts and serializes worker replicas."""
    __tablename__ = "billing_provider_budgets"
    provider = Column(String(50), primary_key=True)
    next_request_at = Column(DateTime(timezone=True), nullable=False)
