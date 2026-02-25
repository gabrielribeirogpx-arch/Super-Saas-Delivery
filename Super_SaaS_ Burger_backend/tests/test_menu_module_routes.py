from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.deps import require_admin_user
from app.models.menu_category import MenuCategory
from app.models.menu_item import MenuItem
from app.models.tenant import Tenant
from app.routers.admin_menu import router as admin_menu_router
from app.routers.public_menu import router as public_menu_router


def _build_client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    db.add(Tenant(id=1, slug="burger", business_name="Burger House", custom_domain="burger.test"))
    db.add(MenuCategory(id=1, tenant_id=1, name="Lanches", sort_order=1, active=True))
    db.add(
        MenuItem(
            id=1,
            tenant_id=1,
            category_id=1,
            name="X-Burger",
            description="Carne e queijo",
            price_cents=2500,
            active=True,
        )
    )
    db.commit()

    app = FastAPI()

    @app.middleware("http")
    async def _inject_tenant(request, call_next):
        request.state.tenant = SimpleNamespace(id=1, slug="burger", business_name="Burger House", custom_domain="burger.test")
        return await call_next(request)

    app.include_router(admin_menu_router)
    app.include_router(public_menu_router)

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_admin_user] = lambda: SimpleNamespace(
        id=7,
        tenant_id=1,
        role="owner",
        active=True,
        email="admin@example.com",
    )

    return TestClient(app)


def test_menu_module_expected_routes_return_success():
    client = _build_client()

    items = client.get("/api/admin/menu/items")
    categories = client.get("/api/admin/menu/categories")
    public_menu = client.get("/public/menu", headers={"host": "burger.servicedelivery.com.br"})

    assert items.status_code == 200
    assert categories.status_code == 200
    assert public_menu.status_code == 200
