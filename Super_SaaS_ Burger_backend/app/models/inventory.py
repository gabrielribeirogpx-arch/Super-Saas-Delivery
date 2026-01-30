from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    name = Column(String, nullable=False)
    unit = Column(String, nullable=False)
    cost_cents = Column(Integer, nullable=False, default=0)
    current_stock = Column(Float, nullable=False, default=0)
    min_stock_level = Column(Float, nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), index=True, nullable=False)
    type = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    reason = Column(String, nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    inventory_item = relationship("InventoryItem")


class MenuItemIngredient(Base):
    __tablename__ = "menu_item_ingredients"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), index=True, nullable=False)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), index=True, nullable=False)
    quantity = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    inventory_item = relationship("InventoryItem")


class ModifierIngredient(Base):
    __tablename__ = "modifier_ingredients"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    modifier_id = Column(Integer, ForeignKey("modifiers.id"), index=True, nullable=False)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), index=True, nullable=False)
    quantity = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    inventory_item = relationship("InventoryItem")
