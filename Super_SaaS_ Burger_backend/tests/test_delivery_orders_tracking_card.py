from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.deps import get_request_tenant_id, require_admin_user
from app.models.admin_user import AdminUser
from app.models.order import Order
from app.routers.orders import router as orders_router


def test_delivery_cards_include_only_their_tenant_driver_and_tracking_token():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine)

    with session_local() as db:
        driver = AdminUser(
            tenant_id=1, email="rider@first.test", name="Entregador da loja",
            password_hash="hash", role="DELIVERY",
        )
        other_driver = AdminUser(
            tenant_id=2, email="rider@second.test", name="Entregador de outra loja",
            password_hash="hash", role="DELIVERY",
        )
        db.add_all([driver, other_driver])
        db.flush()
        driver_id = driver.id
        db.add_all([
            Order(
                tenant_id=1, cliente_nome="Cliente", cliente_telefone="11999999999",
                itens="Pedido", endereco="Rua A", status="OUT_FOR_DELIVERY",
                assigned_delivery_user_id=driver_id, tracking_token="token-loja-1",
            ),
            Order(
                tenant_id=2, cliente_nome="Outro", cliente_telefone="11888888888",
                itens="Pedido", endereco="Rua B", status="OUT_FOR_DELIVERY",
                assigned_delivery_user_id=other_driver.id, tracking_token="token-loja-2",
            ),
        ])
        db.commit()

    app = FastAPI()
    app.include_router(orders_router)

    def override_db():
        with session_local() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_request_tenant_id] = lambda: 1
    app.dependency_overrides[require_admin_user] = lambda: AdminUser(id=99, tenant_id=1, role="admin")

    response = TestClient(app).get("/api/delivery/orders?status=OUT_FOR_DELIVERY")

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["assigned_delivery_user_id"] == driver_id
    assert rows[0]["assigned_delivery_user_name"] == "Entregador da loja"
    assert rows[0]["tracking_token"] == "token-loja-1"
