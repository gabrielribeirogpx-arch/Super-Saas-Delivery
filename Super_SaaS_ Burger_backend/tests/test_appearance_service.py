from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.tenant import Tenant
from app.models.tenant_public_settings import TenantPublicSettings
from app.schemas.appearance import AppearanceSettings
from app.services.appearance_service import appearance_service


def test_update_appearance_does_not_clear_logo_when_logo_not_in_payload():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    tenant = Tenant(slug="tempero", name="Tempero", business_name="Tempero")
    db.add(tenant)
    db.flush()

    settings = TenantPublicSettings(tenant_id=tenant.id, logo_url="https://cdn.example.com/logo.png")
    db.add(settings)
    db.commit()

    payload = AppearanceSettings(primary_color="#ff0000")
    appearance_service.update_appearance(db=db, tenant_id=tenant.id, data=payload)

    updated = db.query(TenantPublicSettings).filter(TenantPublicSettings.tenant_id == tenant.id).first()
    assert updated is not None
    assert updated.logo_url == "https://cdn.example.com/logo.png"

    db.close()
