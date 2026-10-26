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


def test_old_blue_preset_maps_to_red_without_replacing_custom_blue():
    old_default = appearance_service._serialize(AppearanceSettings(primary_color="#2563eb"))
    assert appearance_service.is_legacy_default(old_default, "#2563eb")
    custom_blue = appearance_service._serialize(
        AppearanceSettings(primary_color="#2563eb", secondary_color="#ffffff")
    )
    assert not appearance_service.is_legacy_default(custom_blue, "#2563eb")
    assert AppearanceSettings().primary_color == "#dc2626"


def test_saved_blue_preset_is_presented_as_brand_default_but_custom_blue_remains():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    first = Tenant(slug="legacy-blue", name="Legacy", business_name="Legacy")
    second = Tenant(slug="custom-blue", name="Custom", business_name="Custom")
    db.add_all([first, second])
    db.flush()
    db.add_all([
        TenantPublicSettings(tenant_id=first.id, primary_color="#2563eb", theme=appearance_service._serialize(AppearanceSettings(primary_color="#2563eb"))),
        TenantPublicSettings(tenant_id=second.id, primary_color="#2563eb", theme=appearance_service._serialize(AppearanceSettings(primary_color="#2563eb", secondary_color="#ffffff"))),
    ])
    db.commit()
    assert appearance_service.get_appearance(db, first.id).primary_color == "#dc2626"
    custom = appearance_service.get_appearance(db, second.id)
    assert (custom.primary_color, custom.secondary_color) == ("#2563eb", "#ffffff")
    # The owner can deliberately choose the old blue, even with all other settings at defaults.
    appearance_service.update_appearance(db, first.id, AppearanceSettings(primary_color="#2563eb"))
    assert appearance_service.get_appearance(db, first.id).primary_color == "#2563eb"
    db.close()
