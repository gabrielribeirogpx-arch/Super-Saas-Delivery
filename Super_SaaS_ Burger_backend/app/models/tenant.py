from sqlalchemy import Boolean, Column, DateTime, Integer, String, func

from app.core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True)
    # Campos novos para evolução multi-tenant por subdomínio sem quebrar contratos atuais.
    name = Column(String, nullable=False, default="Loja Padrão")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Campos legados mantidos para total compatibilidade retroativa.
    business_name = Column(String, nullable=False, default="Loja Padrão")
    waba_id = Column(String, unique=True, index=True, nullable=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    custom_domain = Column(String, unique=True, index=True, nullable=True)
    manual_open_status = Column(Boolean, default=True, nullable=False)
    estimated_prep_time = Column(String(50), nullable=True)
