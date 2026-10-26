"""A cancellation is not a refund; manual refunds record money already returned."""
import json

import pytest

from app.models.admin_audit_log import AdminAuditLog
from app.models.finance import CashMovement, OrderPayment
from app.models.order import Order
from test_manual_payments import scenario, confirm, listing


REASON = "Cliente desistiu antes do preparo"


def adjust(s, status="canceled", reason=REASON, *, order_id=1, payment_id=1):
    return s.client.post(f"/api/orders/{order_id}/payments/{payment_id}/status", json={"status":status,"reason":reason,"amount_cents":1,"fee_cents":0})


@pytest.mark.parametrize("role", ["owner","admin","cashier"])
def test_pending_cancel_has_reason_actor_and_no_cash_movement(scenario,role):
    s=scenario;s.actor.user.role=role;s.db.commit()
    r=adjust(s);assert r.status_code==200,r.text
    assert r.json()["status"]=="canceled" and r.json()["paid_at"] is None
    assert s.db.query(CashMovement).count()==0
    assert s.db.get(Order,1).status=="DELIVERED"
    audit=s.db.query(AdminAuditLog).one()
    assert audit.action=="cancel_manual_payment" and audit.user_id==1 and audit.tenant_id==1
    assert json.loads(audit.meta_json)["reason"]==REASON
    assert adjust(s,reason="Outra razão não substitui o original").status_code==200
    assert s.db.query(AdminAuditLog).count()==1
    data=listing(s,status="canceled").json();entry=data["items"][0]
    assert data["canceled_cents"]==2990 and data["pending_cents"]==0
    assert entry["last_adjustment"]["reason"]==REASON
    assert entry["last_adjustment"]["recorded_by"]=="Operador"
    assert entry["last_adjustment"]["recorded_at"].endswith("Z")
    assert not entry["can_cancel"] and not entry["can_refund"] and not entry["can_confirm"]
    assert confirm(s).status_code==409


@pytest.mark.parametrize("method",["cash","money","pix","card"])
def test_full_manual_refund_preserves_receipt_and_adds_one_outflow(scenario,method):
    s=scenario;s.db.get(OrderPayment,1).method=method;s.db.get(OrderPayment,1).fee_cents=50;s.db.commit()
    assert confirm(s).status_code==200
    paid_at=s.db.get(OrderPayment,1).paid_at
    r=adjust(s,"refunded","Valor integral devolvido ao cliente")
    assert r.status_code==200,r.text
    assert adjust(s,"refunded","Repetição da requisição").status_code==200
    assert s.db.get(OrderPayment,1).paid_at==paid_at
    out=s.db.query(CashMovement).filter_by(category="refund").one()
    assert out.amount_cents==2990 and out.type=="out" and out.reference_id==1
    assert "Valor integral devolvido" in out.description
    assert s.db.query(CashMovement).filter_by(category="sale").count()==1
    assert s.db.query(CashMovement).filter_by(category="fee").count()==1
    assert s.db.query(AdminAuditLog).filter_by(action="refund_manual_payment").count()==1
    data=listing(s,status="refunded").json()
    assert data["refunded_cents"]==2990 and data["paid_cents"]==0
    assert data["items"][0]["confirmed_by"]=="Operador"
    assert data["items"][0]["last_adjustment"]["reason"]=="Valor integral devolvido ao cliente"
    assert s.db.get(Order,1).status=="DELIVERED"
    # Fee remains an expense: a manual refund never claims to recover provider fees.
    assert sum(m.amount_cents*(1 if m.type=="in" else -1) for m in s.db.query(CashMovement))==-50


@pytest.mark.parametrize("target", ["canceled","refunded"])
@pytest.mark.parametrize("reason",[None,"","    ","abc","  ab  ","a"*501])
def test_reason_is_required_even_if_browser_is_bypassed(scenario,target,reason):
    s=scenario
    if target=="refunded":assert confirm(s).status_code==200
    before=s.db.query(CashMovement).count()
    assert adjust(s,target,reason).status_code in {409,422}
    assert s.db.query(CashMovement).count()==before
    assert s.db.query(AdminAuditLog).filter_by(action="refund_manual_payment").count()==0
    assert s.db.query(AdminAuditLog).filter_by(action="cancel_manual_payment").count()==0


def test_reason_is_trimmed_and_rendered_as_data(scenario):
    s=scenario
    reason='<script>alert("test")</script>'
    assert adjust(s,reason="  "+reason+"  ").status_code==200
    assert listing(s,status="canceled").json()["items"][0]["last_adjustment"]["reason"]==reason


def test_cannot_cancel_received_payment_or_refund_pending(scenario):
    s=scenario
    assert adjust(s,"refunded").status_code==409
    assert confirm(s).status_code==200
    assert adjust(s,"canceled").status_code==409
    assert s.db.get(OrderPayment,1).status=="paid"
    assert s.db.query(CashMovement).count()==1


@pytest.mark.parametrize("role",["operator","delivery","viewer"])
@pytest.mark.parametrize("target",["canceled","refunded"])
def test_adjustment_requires_financial_role(scenario,role,target):
    s=scenario
    if target=="refunded":assert confirm(s).status_code==200
    s.actor.user.role=role;s.db.commit()
    assert adjust(s,target).status_code==403
    assert s.db.query(AdminAuditLog).filter_by(action="refund_manual_payment").count()==0
    assert s.db.query(AdminAuditLog).filter_by(action="cancel_manual_payment").count()==0


@pytest.mark.parametrize("target",["canceled","refunded"])
def test_cannot_adjust_another_store_or_substitute_payment(scenario,target):
    s=scenario
    assert adjust(s,target,order_id=2,payment_id=2).status_code==403
    assert adjust(s,target,payment_id=2).status_code==404
    assert s.db.query(AdminAuditLog).count()==0


@pytest.mark.parametrize("target",["canceled","refunded"])
def test_adjustment_audit_failure_rolls_back_status_and_cash(scenario,monkeypatch,target):
    import app.services.admin_audit as audit
    s=scenario
    if target=="refunded":assert confirm(s).status_code==200
    before=s.db.query(CashMovement).count()
    def fail(*args,**kwargs):raise RuntimeError("audit unavailable")
    monkeypatch.setattr(audit,"log_admin_action",fail)
    assert adjust(s,target).status_code==500
    s.db.expire_all()
    assert s.db.get(OrderPayment,1).status==("paid" if target=="refunded" else "pending")
    assert s.db.query(CashMovement).count()==before


def test_canceled_order_still_allows_canceling_its_pending_payment(scenario):
    s=scenario;s.db.get(Order,1).status="CANCELADO";s.db.commit()
    entry=listing(s).json()["items"][0]
    assert entry["can_cancel"] and not entry["can_confirm"]
    assert adjust(s).status_code==200
    assert s.db.query(CashMovement).count()==0


@pytest.mark.parametrize("target",["canceled","refunded"])
def test_native_payment_not_manually_adjustable(scenario,target):
    s=scenario
    if target=="refunded":assert confirm(s).status_code==200
    s.db.get(Order,1).payment_method="native_pix";s.db.commit()
    assert adjust(s,target).status_code==409


def test_legacy_adjustment_without_reason_not_fabricated(scenario):
    s=scenario;s.db.get(OrderPayment,1).status="canceled"
    s.db.add(AdminAuditLog(tenant_id=1,user_id=1,action="update_manual_payment_status",entity_type="order_payment",entity_id=1,meta_json=json.dumps({"to_status":"canceled"})))
    s.db.commit()
    entry=listing(s,status="canceled").json()["items"][0]
    assert entry["last_adjustment"]["reason"] is None


def test_manual_refund_does_not_restock_consumed_ingredients(scenario):
    from app.models.inventory import InventoryItem,MenuItemIngredient,InventoryMovement
    from app.models.menu_item import MenuItem
    from app.models.order_item import OrderItem
    s=scenario
    s.db.add(MenuItem(id=1,tenant_id=1,name="Burger",price_cents=2990));s.db.flush()
    s.db.add(InventoryItem(id=1,tenant_id=1,name="Pão",unit="un",current_stock=10,min_stock_level=0));s.db.flush()
    s.db.add(MenuItemIngredient(tenant_id=1,menu_item_id=1,inventory_item_id=1,quantity=1))
    s.db.add(OrderItem(order_id=1,tenant_id=1,menu_item_id=1,name="Burger",quantity=2,unit_price_cents=1495,subtotal_cents=2990));s.db.commit()
    assert confirm(s).status_code==200
    assert adjust(s,"refunded").status_code==200
    assert adjust(s,"refunded").status_code==200
    assert s.db.get(InventoryItem,1).current_stock==8
    assert s.db.query(InventoryMovement).count()==1
