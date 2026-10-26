from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.models.tenant import Tenant
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
