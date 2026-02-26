from typing import Literal, Optional

from pydantic import BaseModel


class AppearanceSettings(BaseModel):
    primary_color: str = "#2563eb"
    secondary_color: str = "#111827"
    button_radius: int = 12
    hero_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    font_family: str = "Inter"
    layout_variant: Literal["clean", "modern", "commercial"] = "clean"
    banner_blur_enabled: bool = True
