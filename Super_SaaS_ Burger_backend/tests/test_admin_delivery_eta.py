from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.deps import require_admin_user
from app.models.admin_user import AdminUser
from app.models.delivery_tracking import DeliveryTracking
from app.models.order import Order
from app.routers.delivery_api import router as delivery_router


def test_admin_eta_uses_admin_session_and_stays_within_its_restaurant():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine)

    with session_local() as db:
        db.add(AdminUser(
            id=1, tenant_id=1, email="owner@first.test", name="Dono",
            password_hash="hash", role="admin",
        ))
        db.add_all([
            Order(
                id=10, tenant_id=1, cliente_nome="Cliente", cliente_telefone="11999999999",
                itens="Pedido", endereco="Rua A", status="OUT_FOR_DELIVERY",
            ),
            Order(
                id=20, tenant_id=2, cliente_nome="Outro", cliente_telefone="11888888888",
                itens="Pedido", endereco="Rua B", status="OUT_FOR_DELIVERY",
            ),
            Order(
                id=30, tenant_id=1, cliente_nome="Sem rota", cliente_telefone="11777777777",
                itens="Pedido", endereco="Rua C", status="OUT_FOR_DELIVERY",
            ),
        ])
        db.flush()
        db.add_all([
            DeliveryTracking(
                order_id=10, estimated_duration_seconds=180,
                expected_delivery_at=datetime.now(timezone.utc),
                route_duration_seconds=180, route_distance_meters=500,
            ),
            DeliveryTracking(
                order_id=20, estimated_duration_seconds=60,
                expected_delivery_at=datetime.now(timezone.utc),
                route_duration_seconds=60, route_distance_meters=100,
            ),
        ])
        db.commit()

    app = FastAPI()
    app.include_router(delivery_router)

    def override_db():
        with session_local() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    assert client.get("/api/delivery/admin/orders/10/eta").status_code == 401

    app.dependency_overrides[require_admin_user] = lambda: AdminUser(
        id=1, tenant_id=1, role="admin"
    )
    own = client.get("/api/delivery/admin/orders/10/eta")
    assert own.status_code == 200
    assert own.json() == {
        "remaining_seconds": 180, "status": "ARRIVING", "distance_meters": 500
    }
    pending = client.get("/api/delivery/admin/orders/30/eta")
    assert pending.status_code == 200
    assert pending.json() == {
        "remaining_seconds": None, "status": None, "distance_meters": None
    }
    assert client.get("/api/delivery/admin/orders/20/eta").status_code == 404
