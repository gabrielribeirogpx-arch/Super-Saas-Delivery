import io

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.models.tenant import Tenant
from app.models.tenant_public_settings import TenantPublicSettings
from app.routers import public_pwa
from app.routers.public_pwa import router


def _client() -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(Tenant(id=1, slug="meuburger", business_name="Meu Burger", is_active=True))
    session.commit()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: session
    return TestClient(app)


def test_manifest_opens_the_store_and_resolves_its_icons_on_a_shared_host():
    client = _client()
    response = client.get("/api/public/pwa/manifest?tenant=meuburger", headers={"host": "staging.fomizero.com.br"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")
    manifest = response.json()
    assert manifest["name"] == "Meu Burger"
    assert manifest["id"] == "/?tenant=meuburger"
    assert manifest["start_url"] == "/loja/meuburger"
    assert manifest["display"] == "standalone"
    assert all("tenant=meuburger" in icon["src"] for icon in manifest["icons"])

    icon = client.get(manifest["icons"][1]["src"], headers={"host": "staging.fomizero.com.br"})
    assert icon.status_code == 200
    assert icon.headers["content-type"] == "image/png"
    assert icon.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_installed_icon_uses_the_restaurant_logo(monkeypatch):
    client = _client()
    db = client.app.dependency_overrides[get_db]()
    db.add(TenantPublicSettings(tenant_id=1, logo_url="https://assets.example/meuburger.png", primary_color="#dc2626"))
    db.commit()
    monkeypatch.setattr(public_pwa, "_load_logo", lambda url: Image.new("RGBA", (100, 100), "#00ff00"))
    public_pwa._ICON_CACHE.clear()

    icon = client.get("/api/public/pwa/icon/192?tenant=meuburger", headers={"host": "staging.fomizero.com.br"})

    assert icon.status_code == 200
    assert icon.headers["cache-control"].startswith("public, max-age=0")
    image = Image.open(io.BytesIO(icon.content)).convert("RGB")
    assert image.getpixel((96, 96)) == (0, 255, 0)
    assert image.getpixel((0, 0)) == (0, 255, 0)


def test_icon_removes_transparent_padding_and_crops_to_square(monkeypatch):
    client = _client()
    db = client.app.dependency_overrides[get_db]()
    db.add(TenantPublicSettings(tenant_id=1, logo_url="https://assets.example/meuburger.png"))
    db.commit()
    logo = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
    logo.paste(Image.new("RGBA", (140, 80), "#00ff00"), (30, 10))
    monkeypatch.setattr(public_pwa, "_load_logo", lambda url: logo)
    public_pwa._ICON_CACHE.clear()

    for icon_path in ("/api/public/pwa/icon/180", "/api/public/pwa/icon/512?purpose=maskable"):
        separator = "&" if "?" in icon_path else "?"
        response = client.get(f"{icon_path}{separator}tenant=meuburger", headers={"host": "staging.fomizero.com.br"})
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
        assert response.status_code == 200
        assert image.getpixel((0, 0)) == (0, 255, 0)
        assert image.getpixel((image.width - 1, image.height - 1)) == (0, 255, 0)
