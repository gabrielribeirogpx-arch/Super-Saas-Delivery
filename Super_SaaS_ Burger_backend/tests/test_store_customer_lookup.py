from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.models.customer import Customer
from app.models.customer_address import CustomerAddress
from app.models.tenant import Tenant
from app.routers import store as store_module
from app.routers.store import router as store_router


def _build_client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = testing_session()
    db.add(Tenant(id=1, slug="tempero", business_name="Tempero"))
    db.add(Customer(id=10, tenant_id=1, name="Maria", phone="16994361408", email="maria@example.com"))
    db.add(
        CustomerAddress(
            id=20,
            customer_id=10,
            cep="14000000",
            street="Rua A",
            number="123",
            complement="Casa",
            neighborhood="Centro",
            city="Ribeirão Preto",
            state="SP",
        )
    )
    db.commit()

    app = FastAPI()

    @app.middleware("http")
    async def _inject_tenant(request, call_next):
        request.state.tenant = SimpleNamespace(id=1)
        return await call_next(request)

    app.include_router(store_router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_customer_by_phone_returns_customer_payload():
    client = _build_client()

    response = client.get("/api/store/customer-by-phone", params={"phone": "16994361408"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is True
    assert payload["exists"] is True
    assert payload["name"] == "Maria"
    assert payload["customer_id"] == 10
    assert payload["customer"]["phone"] == "16994361408"
    assert payload["address"]["street"] == "Rua A"


def test_customer_by_phone_returns_null_when_customer_not_found():
    client = _build_client()

    response = client.get("/api/store/customer-by-phone", params={"phone": "00000000000"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is False
    assert payload["exists"] is False
    assert payload["name"] is None
    assert payload["customer_id"] is None
    assert payload["customer"] is None
    assert payload["address"] is None


def test_store_orders_route_keeps_working(monkeypatch):
    client = _build_client()

    async def _fake_create_order_for_tenant(db, tenant, payload):
        return {
            "order_id": 99,
            "customer_id": None,
            "status": "created",
            "estimated_time": 35,
            "total": 19.9,
            "order_type": "delivery",
            "payment_method": "pix",
            "street": "Rua A",
            "number": "123",
            "complement": None,
            "neighborhood": "Centro",
            "city": "Ribeirão Preto",
            "reference": None,
            "items": [],
        }

    monkeypatch.setattr(store_module, "_create_order_for_tenant", _fake_create_order_for_tenant)

    response = client.post(
        "/api/store/orders",
        json={
            "store_id": 1,
            "customer_name": "Maria",
            "customer_phone": "16994361408",
            "delivery_type": "ENTREGA",
            "payment_method": "pix",
            "items": [{"item_id": 1, "quantity": 1, "selected_modifiers": []}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["order_id"] == 99
    assert payload["status"] == "created"
