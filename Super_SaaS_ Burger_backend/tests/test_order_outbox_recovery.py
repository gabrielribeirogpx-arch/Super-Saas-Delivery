from datetime import timedelta
import json
import pytest
from types import SimpleNamespace

from test_order_durability import sessions, submit, NOW, fake_sender
from app.models.order import Order
from app.models.order_durability import OrderSubmission, OrderOutbox, OrderEffectReceipt
from app.models.whatsapp_message_log import WhatsAppMessageLog
from app.services.order_outbox import enqueue_order_created, enqueue_order_status_changed
from app.services import order_outbox_worker as worker
from app.services.whatsapp_outbound import send_whatsapp_message
from app.whatsapp.service import WhatsAppService


def test_expired_final_lease_enters_review_and_operator_can_retry_only_review(sessions, monkeypatch):
    submit(sessions)
    with sessions() as db, db.begin():
        db.query(OrderOutbox).one().attempts = 7
    claim = worker.claim_one(sessions, NOW)
    assert not worker.retry_review(sessions, claim.id)
    later = NOW + worker.LEASE + timedelta(seconds=1)
    assert worker.claim_one(sessions, later) is None
    assert worker.stats(sessions)["counts"] == {"review": 1}
    assert worker.retry_review(sessions, claim.id)
    monkeypatch.setattr(worker, "send_whatsapp_message", fake_sender([]))
    assert worker.run_cycle(sessions, clock=lambda: later)["done"] == 1


def test_cleanup_is_bounded_keeps_unfinished_work_and_retains_effect_receipts(sessions, monkeypatch):
    submit(sessions)
    monkeypatch.setattr(worker, "send_whatsapp_message", fake_sender([]))
    worker.run_cycle(sessions, clock=lambda: NOW)
    with sessions() as db, db.begin():
        enqueue_order_created(db, db.query(Order).one())
        db.query(OrderSubmission).one().expires_at = NOW - timedelta(days=1)
    result = worker.cleanup(sessions, now=NOW + timedelta(days=8), limit=1)
    assert result == {"receipts_deleted": 1, "jobs_deleted": 1}
    with sessions() as db:
        assert db.query(OrderOutbox).one().status == "pending"
        assert db.query(OrderEffectReceipt).count() == 1
    calls = []
    monkeypatch.setattr(worker, "send_whatsapp_message", fake_sender(calls))
    assert worker.run_cycle(sessions, clock=lambda: NOW + timedelta(days=8))["done"] == 1
    assert calls == []


def test_redis_zero_subscribers_is_success_but_publish_failure_retries(sessions, monkeypatch):
    submit(sessions)
    monkeypatch.setattr(worker, "send_whatsapp_message", fake_sender([]))
    worker.run_cycle(sessions, clock=lambda: NOW)
    with sessions() as db, db.begin():
        order = db.query(Order).one()
        order.status = "DRIVER_ASSIGNED"
        # Existing fixture admin belongs to this tenant, so the FK remains valid.
        order.assigned_delivery_user_id = 1
        enqueue_order_status_changed(db, order, "PRONTO")
    calls = []
    def failed(*args, **kwargs):
        calls.append(kwargs["strict"])
        raise RuntimeError("redis_down")
    monkeypatch.setattr(worker, "publish_delivery_assignment_event", failed)
    assert worker.run_cycle(sessions, clock=lambda: NOW)["retry"] == 1
    monkeypatch.setattr(worker, "publish_delivery_assignment_event", lambda *a, **kw: 0)
    assert worker.run_cycle(sessions, clock=lambda: NOW + timedelta(minutes=1))["done"] == 1
    assert calls == [True]


def test_crash_after_saved_provider_success_does_not_send_again(sessions, monkeypatch):
    submit(sessions)
    def sent_then_crashed(db, **kwargs):
        db.add(WhatsAppMessageLog(tenant_id=kwargs["tenant_id"], direction="out",
            to_phone=kwargs["phone"], template_name=kwargs["template"], message_type="template", status="sent",
            payload_json=json.dumps({"order_id": kwargs["order_id"], "status_stage": kwargs["template"]})))
        db.commit()
        raise RuntimeError("process lost after provider receipt was saved")
    monkeypatch.setattr(worker, "send_whatsapp_message", sent_then_crashed)
    assert worker.run_cycle(sessions, clock=lambda: NOW)["retry"] == 1
    monkeypatch.setattr(worker, "send_whatsapp_message", send_whatsapp_message)
    def forbidden(*_, **__):
        raise AssertionError("provider must not be contacted for a recorded success")
    monkeypatch.setattr(WhatsAppService, "_select_provider", forbidden)
    assert worker.run_cycle(sessions, clock=lambda: NOW + timedelta(minutes=1))["done"] == 1
    with sessions() as db:
        assert db.query(WhatsAppMessageLog).count() == 1
        assert db.query(OrderEffectReceipt).count() == 1


def test_whatsapp_receipt_for_order_ten_does_not_suppress_order_one(sessions):
    with sessions() as db, db.begin():
        db.add(WhatsAppMessageLog(tenant_id=1, direction="out", message_type="template", status="sent",
            template_name="order_confirmed", payload_json=json.dumps({"order_id": 10, "status_stage": "order_confirmed"})))
    with sessions() as db:
        service = WhatsAppService()
        assert not service._is_duplicate_template(db, tenant_id=1, order_id=1, template_name="order_confirmed", status_stage="order_confirmed")
        assert service._is_duplicate_template(db, tenant_id=1, order_id=10, template_name="order_confirmed", status_stage="order_confirmed")


def test_embedded_consumer_defaults_and_invalid_setting_fail_fast(monkeypatch):
    monkeypatch.delenv("ORDER_OUTBOX_EMBEDDED", raising=False)
    monkeypatch.setattr("app.core.config.ENV_NORMALIZED", "production")
    assert worker.embedded_enabled()
    monkeypatch.setattr("app.core.config.ENV_NORMALIZED", "test")
    assert not worker.embedded_enabled()
    monkeypatch.setenv("ORDER_OUTBOX_EMBEDDED", " true ")
    assert worker.embedded_enabled()
    monkeypatch.setenv("ORDER_OUTBOX_EMBEDDED", "false")
    assert not worker.embedded_enabled()
    monkeypatch.setenv("ORDER_OUTBOX_EMBEDDED", "typo")
    with pytest.raises(RuntimeError, match="invalid_order_outbox_embedded"):
        worker.embedded_enabled()
