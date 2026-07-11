from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.routers.onboarding as onboarding_module
from app.core.database import Base, get_db
from app.models.admin_user import AdminUser
from app.models.tenant import Tenant
from app.models.user import User
from app.routers.auth import router as auth_router
from app.routers.onboarding import _normalize_slug, router


def _build_client(raise_server_exceptions: bool = True):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(router)
    app.include_router(auth_router)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app, raise_server_exceptions=raise_server_exceptions), testing_session


def test_normalize_slug_removes_accents_symbols_and_deduplicates_hyphens():
    assert _normalize_slug("Açaí do João - Unidade #1") == "acai-do-joao-unidade-1"
    assert _normalize_slug("  Burger's --- Premium!!! ") == "burgers-premium"


def test_onboarding_returns_slug_with_hyphenated_words():
    client, _ = _build_client()

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
    assert response.json()["slug"] == "loja-legal-premium"


def test_onboarding_generates_predictable_slug_conflicts():
    client, _ = _build_client()

    for index, expected_slug in enumerate(["burgers", "burgers-2", "burgers-3"], start=1):
        response = client.post(
            "/api/onboarding/tenant",
            json={
                "business_name": "Burgers",
                "admin_name": "Admin",
                "admin_email": f"admin-{index}@example.com",
                "admin_password": "12345678",
            },
        )

        assert response.status_code == 201
        assert response.json()["slug"] == expected_slug


def test_onboarding_normalizes_equivalent_burger_names_to_same_base_slug():
    examples = [
        ("Bürgers", "burgers"),
        ("Burger's", "burgers"),
        ("BURGERS", "burgers"),
        ("Meu Restaurante Premium", "meu-restaurante-premium"),
    ]

    for business_name, expected_slug in examples:
        client, _ = _build_client()
        response = client.post(
            "/api/onboarding/tenant",
            json={
                "business_name": business_name,
                "admin_name": "Admin",
                "admin_email": "admin@example.com",
                "admin_password": "12345678",
            },
        )

        assert response.status_code == 201
        assert response.json()["slug"] == expected_slug


def test_onboarding_creates_tenant_created_at_and_owner_in_one_transaction():
    client, testing_session = _build_client()

    response = client.post(
        "/api/onboarding/tenant",
        json={
            "business_name": "Tenant Com Owner",
            "admin_name": "Owner",
            "admin_email": "owner@example.com",
            "admin_password": "12345678",
        },
    )

    assert response.status_code == 201
    tenant_id = response.json()["tenant_id"]

    db = testing_session()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).one()
        owner = db.query(AdminUser).filter(AdminUser.tenant_id == tenant_id).one()
        assert tenant.created_at is not None
        assert owner.email == "owner@example.com"
        assert owner.role == "owner"
    finally:
        db.close()


def test_onboarding_rolls_back_tenant_when_later_step_fails(monkeypatch):
    client, testing_session = _build_client(raise_server_exceptions=False)

    def fail_after_tenant_flush(db, tenant_id):
        raise RuntimeError("forced onboarding failure")

    monkeypatch.setattr(onboarding_module, "_seed_tenant_defaults", fail_after_tenant_flush)

    response = client.post(
        "/api/onboarding/tenant",
        json={
            "business_name": "Rollback Tenant",
            "admin_name": "Owner",
            "admin_email": "rollback@example.com",
            "admin_password": "12345678",
        },
    )

    assert response.status_code == 500
    db = testing_session()
    try:
        assert db.query(Tenant).filter(Tenant.slug == "rollback-tenant").count() == 0
        assert db.query(AdminUser).filter(AdminUser.email == "rollback@example.com").count() == 0
    finally:
        db.close()


def test_auth_register_tenant_flow_still_uses_created_at_default():
    client, testing_session = _build_client()

    response = client.post(
        "/auth/register",
        json={
            "name": "Owner",
            "email": "auth-owner@example.com",
            "password": "123456",
            "business_name": "Auth Tenant",
        },
    )

    assert response.status_code == 201
    tenant_id = response.json()["tenant_id"]
    db = testing_session()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).one()
        user = db.query(User).filter(User.tenant_id == tenant_id).one()
        assert tenant.created_at is not None
        assert user.email == "auth-owner@example.com"
    finally:
        db.close()
