from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ModifierOptionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price_delta: Decimal
    is_default: bool
    is_active: bool
    order_index: int


class ModifierGroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    required: bool
    min_selection: int
    max_selection: int
    options: list[ModifierOptionResponse]


class PublicProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price_cents: int
    image_url: Optional[str] = None
    modifier_groups: list[ModifierGroupResponse] = Field(default_factory=list)


class AdminProductResponse(BaseModel):
    id: int
    tenant_id: int
    category_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    price_cents: int
    image_url: Optional[str] = None
    active: bool
    modifier_groups: list[ModifierGroupResponse] = Field(default_factory=list)
