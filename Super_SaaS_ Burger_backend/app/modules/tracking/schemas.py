from __future__ import annotations

from pydantic import BaseModel, Field


class DriverLocationIn(BaseModel):
    order_id: int
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class DriverLocationOut(BaseModel):
    lat: float
    lng: float
    updated_at: str
