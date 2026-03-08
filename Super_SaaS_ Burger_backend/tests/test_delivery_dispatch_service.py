from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.admin_user import AdminUser
from app.models.order import Order
from app.models.delivery_tracking import DeliveryTracking
from app.routers.delivery_api import get_driver_delivery_snapshot, list_delivery_orders
from app.services.delivery_service import accept_order, complete_delivery, list_available_orders, set_offline


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _delivery_user(*, tenant_id: int, email: str, status: str = "OFFLINE") -> AdminUser:
    return AdminUser(
        tenant_id=tenant_id,
        email=email,
        name="Courier",
        password_hash="hashed",
        role="DELIVERY",
        active=True,
        status=status,
    )


def _order(*, tenant_id: int, status: str = "READY", assigned_delivery_user_id: int | None = None) -> Order:
    return Order(
        tenant_id=tenant_id,
        cliente_nome="Cliente",
        cliente_telefone="5511999999999",
        itens="1x Produto",
        endereco="Rua 1",
        observacao="",
        status=status,
        assigned_delivery_user_id=assigned_delivery_user_id,
    )


def test_offline_delivery_user_cannot_accept_order(db_session):
    courier = _delivery_user(tenant_id=1, email="d1@example.com", status="OFFLINE")
    order = _order(tenant_id=1, status="READY")
    db_session.add_all([courier, order])
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        accept_order(db_session, current_user=courier, order_id=order.id)

    assert exc.value.status_code == 409


def test_delivery_user_cannot_accept_second_active_order(db_session):
    courier = _delivery_user(tenant_id=1, email="d2@example.com", status="ONLINE")
    db_session.add(courier)
    db_session.commit()

    active_order = _order(tenant_id=1, status="OUT_FOR_DELIVERY", assigned_delivery_user_id=courier.id)
    new_order = _order(tenant_id=1, status="READY")
    db_session.add_all([active_order, new_order])
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        accept_order(db_session, current_user=courier, order_id=new_order.id)

    assert exc.value.status_code == 409




def test_delivery_user_with_stale_delivering_status_can_accept_when_no_active_order(db_session):
    courier = _delivery_user(tenant_id=1, email="stale@example.com", status="DELIVERING")
    order = _order(tenant_id=1, status="READY")
    db_session.add_all([courier, order])
    db_session.commit()

    with (
        patch("app.services.delivery_service.emit_order_status_changed"),
        patch("app.services.delivery_service.publish_standard_delivery_status_event"),
    ):
        response = accept_order(db_session, current_user=courier, order_id=order.id)

    db_session.refresh(order)
    db_session.refresh(courier)
    assert response["ok"] is True
    assert order.status == "OUT_FOR_DELIVERY"
    assert order.assigned_delivery_user_id == courier.id
    assert courier.status == "DELIVERING"

def test_delivery_user_cannot_complete_order_from_another_delivery_user(db_session):
    courier = _delivery_user(tenant_id=1, email="d3@example.com", status="DELIVERING")
    other = _delivery_user(tenant_id=1, email="d4@example.com", status="DELIVERING")
    db_session.add_all([courier, other])
    db_session.commit()

    order = _order(tenant_id=1, status="OUT_FOR_DELIVERY", assigned_delivery_user_id=other.id)
    db_session.add(order)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        complete_delivery(db_session, current_user=courier, order_id=order.id)

    assert exc.value.status_code == 409


def test_delivery_user_cannot_go_offline_while_delivering(db_session):
    courier = _delivery_user(tenant_id=1, email="d5@example.com", status="DELIVERING")
    db_session.add(courier)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        set_offline(db_session, current_user=courier)

    assert exc.value.status_code == 409


def test_atomic_order_accept_prevents_race_condition(db_session):
    courier_1 = _delivery_user(tenant_id=1, email="d6@example.com", status="ONLINE")
    courier_2 = _delivery_user(tenant_id=1, email="d7@example.com", status="ONLINE")
    order = _order(tenant_id=1, status="READY")
    db_session.add_all([courier_1, courier_2, order])
    db_session.commit()

    with (
        patch("app.services.delivery_service.emit_order_status_changed"),
        patch("app.services.delivery_service.publish_standard_delivery_status_event"),
    ):
        first = accept_order(db_session, current_user=courier_1, order_id=order.id)

    assert first["ok"] is True

    with pytest.raises(HTTPException) as exc:
        accept_order(db_session, current_user=courier_2, order_id=order.id)

    assert exc.value.status_code == 409

    db_session.refresh(order)
    assert order.assigned_delivery_user_id == courier_1.id




def test_accept_order_is_idempotent_for_same_active_order(db_session):
    courier = _delivery_user(tenant_id=1, email="d13@example.com", status="ONLINE")
    order = _order(tenant_id=1, status="OUT_FOR_DELIVERY", assigned_delivery_user_id=None)
    db_session.add_all([courier, order])
    db_session.commit()

    order.assigned_delivery_user_id = courier.id
    db_session.add(order)
    db_session.commit()

    response = accept_order(db_session, current_user=courier, order_id=order.id)

    db_session.refresh(order)
    db_session.refresh(courier)
    assert response["ok"] is True
    assert response["status"] == "OUT_FOR_DELIVERY"
    assert order.assigned_delivery_user_id == courier.id
    assert courier.status == "DELIVERING"

def test_list_available_orders_returns_only_unassigned_ready_orders(db_session):
    courier = _delivery_user(tenant_id=1, email="d8@example.com", status="ONLINE")
    other = _delivery_user(tenant_id=1, email="d9@example.com", status="ONLINE")
    db_session.add_all([courier, other])
    db_session.commit()

    unassigned_ready = _order(tenant_id=1, status="READY", assigned_delivery_user_id=None)
    assigned_ready = _order(tenant_id=1, status="READY", assigned_delivery_user_id=other.id)
    unassigned_wrong_status = _order(tenant_id=1, status="DELIVERED", assigned_delivery_user_id=None)
    db_session.add_all([unassigned_ready, assigned_ready, unassigned_wrong_status])
    db_session.commit()

    results = list_available_orders(db_session, current_user=courier)

    assert [order.id for order in results] == [unassigned_ready.id]


def test_list_delivery_orders_returns_only_orders_assigned_to_current_delivery_user(db_session):
    courier = _delivery_user(tenant_id=1, email="d10@example.com", status="ONLINE")
    other = _delivery_user(tenant_id=1, email="d11@example.com", status="ONLINE")
    db_session.add_all([courier, other])
    db_session.commit()

    mine = _order(tenant_id=1, status="OUT_FOR_DELIVERY", assigned_delivery_user_id=courier.id)
    others = _order(tenant_id=1, status="OUT_FOR_DELIVERY", assigned_delivery_user_id=other.id)
    unassigned = _order(tenant_id=1, status="READY", assigned_delivery_user_id=None)
    db_session.add_all([mine, others, unassigned])
    db_session.commit()

    results = list_delivery_orders(status="OUT_FOR_DELIVERY", db=db_session, current_user=courier)

    assert [order_payload["id"] for order_payload in results] == [mine.id]


def test_complete_delivery_sets_tracking_completed_at(db_session):
    courier = _delivery_user(tenant_id=1, email="d12@example.com", status="DELIVERING")
    db_session.add(courier)
    db_session.commit()

    order = _order(tenant_id=1, status="OUT_FOR_DELIVERY", assigned_delivery_user_id=courier.id)
    db_session.add(order)
    db_session.commit()

    tracking = DeliveryTracking(
        order_id=order.id,
        delivery_user_id=courier.id,
        estimated_duration_seconds=900,
        expected_delivery_at=order.created_at,
        started_at=order.created_at,
    )
    db_session.add(tracking)
    db_session.commit()

    with (
        patch("app.services.delivery_service.emit_order_status_changed"),
        patch("app.services.delivery_service.publish_standard_delivery_status_event"),
        patch("app.services.delivery_service.publish_public_tracking_event"),
    ):
        response = complete_delivery(db_session, current_user=courier, order_id=order.id)

    db_session.refresh(tracking)
    db_session.refresh(courier)
    assert response["status"] == "DELIVERED"
    assert tracking.completed_at is not None
    assert courier.status == "ONLINE"


def test_driver_snapshot_returns_active_delivery_for_saiu_status(db_session):
    courier = _delivery_user(tenant_id=1, email="snapshot@example.com", status="DELIVERING")
    db_session.add(courier)
    db_session.commit()

    order = _order(tenant_id=1, status="SAIU", assigned_delivery_user_id=courier.id)
    db_session.add(order)
    db_session.commit()

    snapshot = get_driver_delivery_snapshot(db=db_session, current_user=courier)

    assert snapshot["active_delivery"] is not None
    assert snapshot["active_delivery"]["id"] == order.id
    assert snapshot["active_delivery"]["status"] == "SAIU"
    assert snapshot["out_for_delivery_count"] == 1


def test_driver_snapshot_returns_null_when_driver_has_no_delivery_order(db_session):
    courier = _delivery_user(tenant_id=1, email="snapshot-empty@example.com", status="ONLINE")
    db_session.add(courier)
    db_session.commit()

    snapshot = get_driver_delivery_snapshot(db=db_session, current_user=courier)

    assert snapshot["active_delivery"] is None
    assert snapshot["out_for_delivery_count"] == 0
