"""Real row-lock tests, only on the existing disposable PostgreSQL CI database."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from app.models.admin_audit_log import AdminAuditLog
from app.models.finance import CashMovement, OrderPayment
from app.models.order import Order
from app.services.finance import create_order_payment, transition_manual_payment, validate_manual_allocation
from test_native_payment_postgresql import pg_database


def test_pg_simultaneous_confirmation_posts_once(pg_database):
    _, sessions, _ = pg_database
    with sessions() as db, db.begin():
        payment = create_order_payment(db, db.get(Order, 1), "cash", 10000, fee_cents=100, status="pending")
        payment_id = payment.id
    barrier = Barrier(2)
    def worker():
        with sessions() as db, db.begin():
            barrier.wait(timeout=15)
            order = db.query(Order).filter_by(id=1,tenant_id=1).populate_existing().with_for_update().one()
            payment = db.query(OrderPayment).filter_by(id=payment_id,tenant_id=1).populate_existing().one()
            return transition_manual_payment(db,order,payment,"paid",user_id=1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: worker(),range(2)))
    assert sorted(results)==[False,True]
    with sessions() as db:
        assert db.query(CashMovement).filter_by(category="sale").count()==1
        assert db.query(CashMovement).filter_by(category="fee").count()==1
        assert db.query(AdminAuditLog).filter_by(action="confirm_manual_payment").count()==1
        assert db.get(OrderPayment,payment_id).paid_at is not None


def test_pg_simultaneous_registration_cannot_overallocate(pg_database):
    _,sessions,_=pg_database
    barrier=Barrier(2)
    def worker():
        with sessions() as db:
            try:
                barrier.wait(timeout=15)
                order=db.query(Order).filter_by(id=1,tenant_id=1).populate_existing().with_for_update().one()
                validate_manual_allocation(db,order,10000)
                create_order_payment(db,order,"cash",10000,status="paid")
                db.commit()
                return "created"
            except ValueError:
                db.rollback()
                return "blocked"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:worker(),range(2)))
    assert sorted(results)==["blocked","created"]
    with sessions() as db:
        assert db.query(OrderPayment).count()==1
        assert db.query(CashMovement).filter_by(category="sale").count()==1
