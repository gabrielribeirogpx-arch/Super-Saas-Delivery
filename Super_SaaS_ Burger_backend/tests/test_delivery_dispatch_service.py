from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.admin_user import AdminUser
from app.models.order import Order
from app.services.delivery_service import accept_order, complete_delivery, set_offline


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
