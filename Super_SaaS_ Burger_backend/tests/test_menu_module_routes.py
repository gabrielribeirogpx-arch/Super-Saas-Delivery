import json
from datetime import datetime, timedelta, timezone
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
from app.models.modifier_group import ModifierGroup
from app.models.modifier_option import ModifierOption
from app.models.customer_address import CustomerAddress
from app.models.customer_email_account import CustomerEmailAccount
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.tenant import Tenant
from app.routers.admin_menu import router as admin_menu_router
from app.routers.kds import router as kds_router
from app.routers import customer_auth, driver_api, public_menu as public_menu_module
from app.routers.public_menu import router as public_menu_router
from app.routers.public_tracking import router as public_tracking_router
from app.services import auth


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
    app.include_router(kds_router)
    app.include_router(public_tracking_router)

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


def test_kds_ready_order_stays_visible_until_it_leaves_the_kitchen():
    client = _build_client()
    response = client.post(
        "/public/orders",
        headers={"host": "burger.servicedelivery.com.br"},
        json={
            "customer_name": "Maria",
            "customer_phone": "5511999999999",
            "order_type": "pickup",
            "payment_method": "cash",
            "products": [{"product_id": 1, "quantity": 1}],
        },
    )
    assert response.status_code == 200
    db = client.app.dependency_overrides[get_db]()
    order_id = db.query(Order.id).scalar()
    assert order_id is not None

    ready = client.post(f"/api/kds/orders/{order_id}/ready?area=COZINHA")
    assert ready.status_code == 200
    assert ready.json()["status"] == "PRONTO"

    listed = client.get("/api/kds/orders?area=COZINHA")
    assert listed.status_code == 200
    assert [order["id"] for order in listed.json()] == [order_id]
    assert listed.json()[0]["status"] == "PRONTO"
    assert listed.json()[0]["ready_areas"] == ["COZINHA"]

    db.query(Order).filter(Order.id == order_id).update({"status": "DELIVERED"})
    db.commit()
    assert client.get("/api/kds/orders?area=COZINHA").json() == []




def test_admin_menu_delete_item_soft_deletes_and_hides_from_listing():
    client = _build_client()

    delete_response = client.delete("/api/admin/menu/items/1")
    assert delete_response.status_code == 200
    assert delete_response.json()["active"] is False

    items_response = client.get("/api/admin/menu/items")
    assert items_response.status_code == 200
    assert items_response.json() == []

    db = client.app.dependency_overrides[get_db]()
    db_item = db.query(MenuItem).filter(MenuItem.id == 1).first()
    assert db_item is not None
    assert db_item.active is False


def test_admin_can_move_item_to_no_category_from_mobile_editor():
    client = _build_client()

    response = client.put(
        "/api/admin/menu/items/1",
        data={"tenant_id": "1", "name": "X-Burger", "price_cents": "2500", "category_id": "-1", "active": "true"},
    )

    assert response.status_code == 200
    assert response.json()["category_id"] is None
    listed = client.get("/api/admin/menu/items")
    assert listed.status_code == 200
    assert listed.json()[0]["category_id"] is None

def test_public_order_tracking_fetches_new_order_immediately():
    client = _build_client()

    payload = {
        "customer_name": "Maria",
        "customer_phone": "5511999999999",
        "order_type": "delivery",
        "street": "Rua A",
        "number": "123",
        "neighborhood": "Centro",
        "city": "São Paulo",
        "state": "SP",
        "payment_method": "cash",
        "delivery_address": {"zip": "01310-100"},
        "products": [{"product_id": 1, "quantity": 1}],
    }

    order_response = client.post("/public/orders", json=payload, headers={"host": "burger.servicedelivery.com.br"})

    assert order_response.status_code == 200
    order_payload = order_response.json()
    tracking_token = order_payload["tracking_token"]
    assert tracking_token
    assert tracking_token == tracking_token.strip()

    db = client.app.dependency_overrides[get_db]()
    created_order = db.query(Order).filter(Order.tracking_token == tracking_token).first()
    assert created_order is not None
    assert created_order.tenant_id == 1

    tracking_response = client.get(
        f"/api/public/order/{tracking_token}",
        headers={"host": "burger.servicedelivery.com.br", "x-tenant-id": "burger"},
    )

    assert tracking_response.status_code == 200
    tracking_payload = tracking_response.json()
    assert "order_id" not in tracking_payload
    assert tracking_token != str(created_order.id)
    assert tracking_payload["order_number"] == order_payload["order_number"]
    assert tracking_payload["status"] == "pending"


def test_public_order_creation_returns_resolved_modifiers_and_kds_payload():
    client = _build_client()

    # Seed modifier setup for the existing menu item
    db = client.app.dependency_overrides[get_db]()
    db.add(
        ModifierGroup(
            id=10,
            tenant_id=1,
            product_id=1,
            name="Tamanho",
            required=True,
            min_selection=1,
            max_selection=1,
            active=True,
        )
    )
    db.add(
        ModifierOption(
            id=100,
            group_id=10,
            name="Grande",
            price_delta=3.50,
            is_active=True,
        )
    )
    db.commit()

    payload = {
        "customer_name": "Maria",
        "customer_phone": "5511999999999",
        "order_type": "delivery",
        "street": "Rua A",
        "number": "123",
        "complement": "Ap 8",
        "neighborhood": "Centro",
        "city": "São Paulo",
        "reference": "Próximo à praça",
        "payment_method": "cash",
        "change_for": "50",
        "delivery_address": {"zip": "01310-100"},
        "products": [
            {
                "product_id": 1,
                "quantity": 2,
                "selected_modifiers": [
                    {"group_id": 10, "option_id": 100}
                ],
            }
        ],
    }

    order_response = client.post("/public/orders", json=payload, headers={"host": "burger.servicedelivery.com.br"})

    assert order_response.status_code == 200
    data = order_response.json()
    assert data["order_type"] == "delivery"
    assert data["payment_method"] == "cash"
    assert data["street"] == "Rua A"
    assert data["number"] == "123"
    assert data["complement"] == "Ap 8"
    assert data["neighborhood"] == "Centro"
    assert data["city"] == "São Paulo"
    assert data["reference"] == "Próximo à praça"
    assert data["items"] == [
        {
            "item_name": "X-Burger",
            "quantity": 2,
            "modifiers": [{"group_name": "Tamanho", "option_name": "Grande"}],
        }
    ]

    kds_response = client.get("/api/kds/orders?area=COZINHA", headers={"host": "burger.servicedelivery.com.br"})
    assert kds_response.status_code == 200
    kds_data = kds_response.json()
    assert len(kds_data) == 1
    assert kds_data[0]["order_type"] == "delivery"
    assert kds_data[0]["payment_method"] == "cash"
    assert kds_data[0]["street"] == "Rua A"
    assert kds_data[0]["address"] == {
        "street": "Rua A",
        "number": "123",
        "neighborhood": "Centro",
        "city": "São Paulo",
        "reference": "Próximo à praça",
    }
    assert kds_data[0]["resolved_items"] == [
        {
            "id": kds_data[0]["resolved_items"][0]["id"],
            "item_name": "X-Burger",
            "quantity": 2,
            "modifiers": [
                {
                    "group_name": "Tamanho",
                    "option_name": "Grande",
                }
            ],
            "production_area": "COZINHA",
        }
    ]

    created_item = db.query(OrderItem).first()
    assert created_item is not None
    assert json.loads(created_item.modifiers_json) == [
        {
            "group_id": 10,
            "option_id": 100,
            "group_name": "Tamanho",
            "option_name": "Grande",
            "name": "Grande",
            "price_cents": 350,
        }
    ]



def test_public_order_creation_with_item_level_selected_modifiers_shows_up_in_kds():
    client = _build_client()

    db = client.app.dependency_overrides[get_db]()
    db.add(
        ModifierGroup(
            id=10,
            tenant_id=1,
            product_id=1,
            name="Tamanho",
            required=True,
            min_selection=1,
            max_selection=1,
            active=True,
        )
    )
    db.add(
        ModifierOption(
            id=100,
            group_id=10,
            name="Grande",
            price_delta=3.50,
            is_active=True,
        )
    )
    db.commit()

    payload = {
        "customer_name": "Paula",
        "customer_phone": "5511977776666",
        "order_type": "delivery",
        "payment_method": "pix",
        "delivery_address": {"zip": "01310-100"},
        "items": [
            {
                "item_id": 1,
                "quantity": 1,
                "selected_modifiers": [
                    {"group_id": 10, "option_id": 100}
                ],
            }
        ],
    }

    order_response = client.post("/public/orders", json=payload, headers={"host": "burger.servicedelivery.com.br"})

    assert order_response.status_code == 200
    data = order_response.json()
    assert data["items"] == [
        {
            "item_name": "X-Burger",
            "quantity": 1,
            "modifiers": [{"group_name": "Tamanho", "option_name": "Grande"}],
        }
    ]

    kds_response = client.get("/api/kds/orders?area=COZINHA", headers={"host": "burger.servicedelivery.com.br"})
    assert kds_response.status_code == 200
    kds_data = kds_response.json()
    assert len(kds_data) == 1
    assert kds_data[0]["resolved_items"][0]["modifiers"] == [
        {
            "group_name": "Tamanho",
            "option_name": "Grande",
        }
    ]

    created_item = db.query(OrderItem).first()
    assert created_item is not None
    assert created_item.modifiers != []


def test_public_order_creation_maps_structured_address_from_delivery_address_payload():
    client = _build_client()

    payload = {
        "customer_name": "João",
        "customer_phone": "5511988887777",
        "order_type": "delivery",
        "payment_method": "pix",
        "products": [
            {"product_id": 1, "quantity": 1}
        ],
        "delivery_address": {
            "street": "Rua B",
            "number": "45",
            "complement": "Casa",
            "district": "Bela Vista",
            "city": "São Paulo",
            "reference": "Portão azul",
            "zip": "01310-100",
        },
    }

    order_response = client.post("/public/orders", json=payload, headers={"host": "burger.servicedelivery.com.br"})

    assert order_response.status_code == 200
    data = order_response.json()
    assert data["street"] == "Rua B"
    assert data["number"] == "45"
    assert data["complement"] == "Casa"
    assert data["neighborhood"] == "Bela Vista"
    assert data["city"] == "São Paulo"
    assert data["reference"] == "Portão azul"


def test_public_order_creation_falls_back_state_and_persists_customer_address_state():
    client = _build_client()

    payload = {
        "customer_name": "João",
        "customer_phone": "5511988887777",
        "order_type": "delivery",
        "payment_method": "pix",
        "products": [{"product_id": 1, "quantity": 1}],
        "delivery_address": {
            "zip": "14813132",
            "street": "Rua Rio de Janeiro",
            "number": "67",
            "complement": "casa",
            "district": "Jardim Brasil",
            "city": "Gavião Peixoto",
            "state": "",
        },
    }

    order_response = client.post("/public/orders", json=payload, headers={"host": "burger.servicedelivery.com.br"})

    assert order_response.status_code == 200

    db = client.app.dependency_overrides[get_db]()
    customer_address = db.query(CustomerAddress).first()
    assert customer_address is not None
    assert customer_address.state == "SP"


def test_public_order_creation_does_not_fail_when_payment_side_effect_breaks(monkeypatch):
    client = _build_client()

    def _raise_payment_error(db, order, payment_method):
        raise RuntimeError("payment provider unavailable")

    monkeypatch.setattr(public_menu_module, "maybe_create_payment_for_order", _raise_payment_error)

    payload = {
        "customer_name": "João",
        "customer_phone": "5511988887777",
        "order_type": "delivery",
        "payment_method": "pix",
        "products": [{"product_id": 1, "quantity": 1}],
        "delivery_address": {"zip": "14813132"},
    }

    order_response = client.post("/public/orders", json=payload, headers={"host": "burger.servicedelivery.com.br"})

    assert order_response.status_code == 200
    response_payload = order_response.json()
    assert response_payload["order_number"] > 0


def test_public_order_tracking_compat_route_without_api_prefix():
    client = _build_client()

    payload = {
        "customer_name": "Maria",
        "customer_phone": "5511999999999",
        "order_type": "delivery",
        "street": "Rua A",
        "number": "123",
        "neighborhood": "Centro",
        "city": "São Paulo",
        "state": "SP",
        "payment_method": "cash",
        "delivery_address": {"zip": "01310-100"},
        "products": [{"product_id": 1, "quantity": 1}],
    }

    order_response = client.post("/public/orders", json=payload, headers={"host": "burger.servicedelivery.com.br"})
    assert order_response.status_code == 200
    tracking_token = order_response.json()["tracking_token"]

    tracking_response = client.get(f"/public/order/{tracking_token}", headers={"host": "burger.servicedelivery.com.br"})
    assert tracking_response.status_code == 200
    tracking_payload = tracking_response.json()
    assert tracking_payload["order_number"] > 0
    assert tracking_payload["status"] == "pending"


def test_kds_and_driver_queues_are_oldest_first_with_id_tie_break():
    client = _build_client()
    db = client.app.dependency_overrides[get_db]()
    earlier = datetime(2026, 11, 21, 12, tzinfo=timezone.utc)
    later = earlier + timedelta(seconds=1)
    specs = [
        (1, 1, later, "PRONTO", None),
        (2, 1, earlier, "PRONTO", None),
        (3, 1, earlier, "PRONTO", None),
        (4, 2, earlier, "PRONTO", None),
        (5, 1, later, "DRIVER_ASSIGNED", 9),
        (6, 1, earlier, "DRIVER_ASSIGNED", 9),
        (7, 1, later, "OUT_FOR_DELIVERY", 9),
    ]
    for order_id, tenant_id, created_at, status, driver_id in specs:
        db.add(Order(id=order_id, tenant_id=tenant_id, created_at=created_at, status=status,
                     assigned_delivery_user_id=driver_id, cliente_telefone="11988887777",
                     itens="Lanche", valor_total=1000))
    db.flush()
    for order_id, tenant_id, *_ in specs[:4]:
        db.add(OrderItem(order_id=order_id, tenant_id=tenant_id, name="Lanche", production_area="COZINHA"))
    db.commit()

    result = client.get("/api/kds/orders?area=COZINHA")
    assert result.status_code == 200
    assert [order["id"] for order in result.json()] == [2, 3, 1]
    state = driver_api.get_driver_state(db, SimpleNamespace(id=9, tenant_id=1, name="Entregador", email="driver@example.test"))
    assert [order["id"] for order in state["available_orders"]] == [2, 3, 1]
    assert [order["id"] for order in state["assigned_orders"]] == [6, 5, 7]
    assert state["active_delivery"]["id"] == 7


def test_email_checkout_saves_address_only_for_verified_account(monkeypatch):
    client = _build_client()
    client.app.include_router(customer_auth.router)
    db = client.app.dependency_overrides[get_db]()
    monkeypatch.setattr(auth, "JWT_SECRET_KEY", "synthetic-checkout-test-key")
    monkeypatch.setattr(customer_auth, "resolve_tenant", lambda request, session: request.state.tenant)

    async def no_geocoding(_address):
        return None, None

    monkeypatch.setattr(public_menu_module, "geocode_address", no_geocoding)
    email = "cliente@example.test"
    phone = "+5511988887777"
    account = CustomerEmailAccount(
        tenant_id=1, email_normalized=email, phone_normalized=phone,
        name="Cliente da conta", verified_at=datetime.now(timezone.utc),
    )
    db.add(account)
    db.commit()
    profile_url = "/api/public/customer-auth/checkout-profile"
    payload = {
        "customer_name": account.name,
        "customer_phone": phone,
        "customer_email": email,
        "delivery_type": "ENTREGA",
        "payment_method": "cash",
        "delivery_address": {
            "zip": "01001000", "street": "Rua do Cliente", "number": "20",
            "neighborhood": "Centro", "city": "São Paulo", "state": "SP",
        },
        "products": [{"product_id": 1, "quantity": 1}],
    }

    assert client.post("/public/orders", json=payload).status_code == 200
    assert client.get(profile_url).status_code == 401
    client.cookies.set(customer_auth.COOKIE_NAME, auth.create_access_token(email, extra={
        "type": "customer_email", "email_verified": True, "email": email, "tenant_id": 1,
    }))
    profile = client.get(profile_url)
    assert profile.json()["addresses"] == []
    assert "no-store" in profile.headers["Cache-Control"]

    history_url = "/api/public/customer-auth/orders"
    assert len(client.get(history_url).json()) == 1
    order = client.post("/public/orders", json={**payload, "customer_email": ""})
    assert order.status_code == 200, order.text
    profile = client.get(profile_url).json()
    assert profile["phone"] == phone
    assert profile["email"] == email
    assert profile["addresses"][0]["street"] == "Rua do Cliente"
    assert profile["addresses"][0]["is_default"] is True
    assert client.get(history_url).json()[0]["tracking_token"] == order.json()["tracking_token"]
