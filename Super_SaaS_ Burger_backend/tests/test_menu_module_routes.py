import json
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
from app.models.order_item import OrderItem
from app.models.tenant import Tenant
from app.routers.admin_menu import router as admin_menu_router
from app.routers.kds import router as kds_router
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
    app.include_router(kds_router)

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



def test_public_order_creation_with_item_level_selected_modifiers_as_strings_shows_up_in_kds():
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
        "items": [
            {
                "item_id": 1,
                "quantity": 1,
                "selected_modifiers": [
                    {"group_id": "10", "option_id": "100"}
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
