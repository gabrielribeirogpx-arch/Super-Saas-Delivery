from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.routers.onboarding import _normalize_slug, router


def _build_client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_normalize_slug_removes_accents_symbols_and_hyphens():
    assert _normalize_slug("Açaí do João - Unidade #1") == "acaidojoaounidade1"


def test_onboarding_returns_slug_without_hyphen():
    client = _build_client()

    response = client.post(
        "/api/onboarding/tenant",
        json={
            "business_name": "Loja Legal Premium",
            "admin_name": "Admin",
            "admin_email": "admin@example.com",
            "admin_password": "12345678",
        },
    )

    assert response.status_code == 201
    assert response.json()["slug"] == "lojalegalpremium"
