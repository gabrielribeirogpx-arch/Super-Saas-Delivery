from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func

from app.core.database import Base


class TenantPublicSettings(Base):
    __tablename__ = "tenant_public_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="ux_tenant_public_settings_tenant_id"),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True, unique=True)
    cover_image_url = Column(Text, nullable=True)
    cover_video_url = Column(Text, nullable=True)
    logo_url = Column(Text, nullable=True)
    theme = Column(String(255), nullable=True)
    primary_color = Column(String(255), nullable=True)
    is_open = Column(Boolean, nullable=False, default=True)
    estimated_time_min = Column(Integer, nullable=True)
    banner_blur_enabled = Column(Boolean, nullable=False, default=True)
    banner_blur_intensity = Column(Integer, nullable=True)
    banner_overlay_opacity = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
