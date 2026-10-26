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


def test_pg_simultaneous_refunds_post_one_outflow_and_preserve_first_reason(pg_database):
    _,sessions,_=pg_database
    with sessions() as db,db.begin():
        payment=create_order_payment(db,db.get(Order,1),"cash",10000,status="paid")
        payment_id=payment.id
    barrier=Barrier(2)
    def worker(reason):
        with sessions() as db,db.begin():
            barrier.wait(timeout=15)
            order=db.query(Order).filter_by(id=1,tenant_id=1).populate_existing().with_for_update().one()
            payment=db.query(OrderPayment).filter_by(id=payment_id,tenant_id=1).populate_existing().one()
            return transition_manual_payment(db,order,payment,"refunded",user_id=1,reason=reason)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(worker,["Devolução feita no caixa", "Pedido de reenvio da mesma devolução"]))
    assert sorted(results)==[False,True]
    with sessions() as db:
        assert db.get(OrderPayment,payment_id).status=="refunded"
        assert db.query(CashMovement).filter_by(category="refund").count()==1
        assert db.query(AdminAuditLog).filter_by(action="refund_manual_payment").count()==1
        assert sum(m.amount_cents*(1 if m.type=="in" else -1) for m in db.query(CashMovement))==0


def test_pg_confirmation_racing_cancellation_has_one_winner(pg_database):
    _,sessions,_=pg_database
    with sessions() as db,db.begin():
        payment=create_order_payment(db,db.get(Order,1),"cash",10000,status="pending")
        payment_id=payment.id
    barrier=Barrier(2)
    def worker(target):
        with sessions() as db:
            try:
                barrier.wait(timeout=15)
                order=db.query(Order).filter_by(id=1,tenant_id=1).populate_existing().with_for_update().one()
                payment=db.query(OrderPayment).filter_by(id=payment_id,tenant_id=1).populate_existing().one()
                transition_manual_payment(db,order,payment,target,user_id=1,reason="Cancelamento solicitado no caixa")
                db.commit()
                return target
            except ValueError:
                db.rollback()
                return "blocked"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(worker,["paid","canceled"]))
    assert results.count("blocked")==1
    with sessions() as db:
        state=db.get(OrderPayment,payment_id).status
        assert state in {"paid","canceled"}
        assert db.query(CashMovement).count()==(1 if state=="paid" else 0)
        assert db.query(AdminAuditLog).count()==1
