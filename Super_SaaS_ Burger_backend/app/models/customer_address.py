from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class CustomerAddress(Base):
    __tablename__ = "customer_addresses"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    street = Column(String(150), nullable=False)
    number = Column(String(20), nullable=False)
    district = Column(String(100), nullable=False)
    city = Column(String(100), nullable=False)
    zip = Column(String(20), nullable=False)
    complement = Column(String(150), nullable=True)

    customer = relationship("Customer", back_populates="addresses")
