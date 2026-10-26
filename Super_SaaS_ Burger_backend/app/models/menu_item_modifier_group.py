from sqlalchemy import Column, ForeignKey, Index, Integer

from app.core.database import Base


class MenuItemModifierGroup(Base):
    __tablename__ = "menu_item_modifier_groups"
    __table_args__ = (
        Index(
            "ix_menu_item_modifier_groups_item_group",
            "tenant_id",
            "menu_item_id",
            "modifier_group_id",
            unique=True,
        ),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    modifier_group_id = Column(Integer, ForeignKey("modifier_groups.id"), nullable=False)
