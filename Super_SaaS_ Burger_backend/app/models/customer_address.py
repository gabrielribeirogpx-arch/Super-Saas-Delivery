from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class CustomerAddress(Base):
    __tablename__ = "customer_addresses"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    zip = Column(String(20), nullable=False)
    cep = Column(String(20), nullable=False)
    street = Column(String(150), nullable=False)
    number = Column(String(20), nullable=False)
    complement = Column(String(150), nullable=True)
    district = Column(String(100), nullable=False, default="")
    neighborhood = Column(String(100), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(2), nullable=True)
    is_default = Column(Boolean, nullable=False, default=False, server_default="0")

    customer = relationship("Customer", back_populates="addresses")
