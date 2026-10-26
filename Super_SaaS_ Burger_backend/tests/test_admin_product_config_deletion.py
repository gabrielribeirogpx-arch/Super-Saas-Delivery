from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.deps import require_admin_user
from app.models.menu_item import MenuItem
from app.models.modifier_group import ModifierGroup
from app.models.modifier_option import ModifierOption
from app.models.tenant import Tenant
from app.routers.admin_product_config import router as admin_product_config_router


def _build_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = testing_session_local()
    db.add(Tenant(id=1, slug="tenant-1", business_name="Tenant 1"))
    db.add(Tenant(id=2, slug="tenant-2", business_name="Tenant 2"))
    db.add(MenuItem(id=1, tenant_id=1, name="Burger", price_cents=1200, active=True))
    db.add(MenuItem(id=2, tenant_id=2, name="Pizza", price_cents=1800, active=True))
    db.add(
        ModifierGroup(
            id=10,
            tenant_id=1,
            product_id=1,
            name="Tamanho",
            required=False,
            min_selection=0,
            max_selection=1,
            active=True,
        )
    )
    db.add(ModifierOption(id=100, group_id=10, name="Grande", price_delta=3.50, is_active=True))
    db.commit()

    app = FastAPI()

    @app.middleware("http")
    async def _inject_tenant(request, call_next):
        request.state.tenant = SimpleNamespace(id=1)
        return await call_next(request)

    app.include_router(admin_product_config_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_admin_user] = lambda: SimpleNamespace(
        id=7,
        tenant_id=1,
        role="owner",
        active=True,
        email="admin@example.com",
    )

    return TestClient(app), db


def test_delete_modifier_option_soft_deletes_option():
    client, db = _build_client()

    response = client.delete("/api/admin/modifier-options/100")

    assert response.status_code == 200
    option = db.query(ModifierOption).filter(ModifierOption.id == 100).first()
    assert option is not None
    assert option.is_active is False


def test_delete_modifier_group_soft_deletes_group_and_options():
    client, db = _build_client()

    response = client.delete("/api/admin/modifier-groups/10")

    assert response.status_code == 200
    group = db.query(ModifierGroup).filter(ModifierGroup.id == 10).first()
    option = db.query(ModifierOption).filter(ModifierOption.id == 100).first()
    assert group is not None
    assert option is not None
    assert group.active is False
    assert option.is_active is False


def test_delete_modifier_group_blocks_other_tenant():
    client, db = _build_client()

    db.add(
        ModifierGroup(
            id=20,
            tenant_id=2,
            product_id=2,
            name="Borda",
            required=False,
            min_selection=0,
            max_selection=1,
            active=True,
        )
    )
    db.commit()

    response = client.delete("/api/admin/modifier-groups/20")

    assert response.status_code == 404
    group = db.query(ModifierGroup).filter(ModifierGroup.id == 20).first()
    assert group is not None
    assert group.active is True
