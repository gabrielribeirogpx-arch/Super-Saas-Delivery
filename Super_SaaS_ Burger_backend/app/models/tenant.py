from sqlalchemy import Boolean, Column, Integer, String
from app.core.database import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True)
    business_name = Column(String, nullable=False, default="Loja Padrão")
    waba_id = Column(String, unique=True, index=True, nullable=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    custom_domain = Column(String, unique=True, index=True, nullable=True)
    manual_open_status = Column(Boolean, default=True, nullable=False)
