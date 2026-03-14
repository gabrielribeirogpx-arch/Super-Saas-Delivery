from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.models.customer import Customer
from app.models.customer_address import CustomerAddress
from app.models.menu_item import MenuItem
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
    db.add(MenuItem(id=1, tenant_id=1, name="X-Burger", description="", price_cents=2500, active=True))
    db.add(Customer(id=10, tenant_id=1, name="Maria", phone="16994361408", email="maria@example.com"))
    db.add(
        CustomerAddress(
            id=20,
            customer_id=10,
            zip="14000000",
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

    app.include_router(store_router, prefix="/api/store")
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


def test_customer_by_phone_accepts_masked_phone():
    client = _build_client()

    response = client.get("/api/store/customer-by-phone", params={"phone": "(16) 99436-1408"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is True
    assert payload["customer"]["phone"] == "16994361408"


def test_store_order_creates_new_customer_and_address_with_zip():
    client = _build_client()

    response = client.post(
        "/api/store/orders",
        json={
            "store_id": 1,
            "customer_name": "Cliente Novo",
            "customer_phone": "(16) 99123-4567",
            "customer_email": "novo@example.com",
            "order_type": "delivery",
            "payment_method": "pix",
            "delivery_address": {
                "zip": "14813132",
                "street": "Rua Rio de Janeiro",
                "number": "67",
                "complement": "casa",
                "district": "Jardim Brasil",
                "city": "Gavião Peixoto",
                "state": "SP",
            },
            "products": [{"product_id": 1, "quantity": 1}],
        },
    )

    assert 200 <= response.status_code < 300

    db = client.app.dependency_overrides[get_db]()
    created_customer = db.query(Customer).filter(Customer.phone == "16991234567").order_by(Customer.id.desc()).first()
    assert created_customer is not None

    customer_address = (
        db.query(CustomerAddress)
        .filter(CustomerAddress.customer_id == created_customer.id)
        .order_by(CustomerAddress.id.desc())
        .first()
    )
    assert customer_address is not None
    assert customer_address.cep == "14813132"
    assert customer_address.zip == "14813132"
