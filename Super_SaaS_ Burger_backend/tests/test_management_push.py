from datetime import timedelta
from uuid import uuid4

import pytest

from app.models.admin_user import AdminUser
from app.models.management_push import ManagementPushDevice
from app.models.order_durability import OrderOutbox
from app.routers import management_push as router
from app.services import management_push, order_outbox_worker as worker
from test_order_durability import NOW, fake_sender, sessions, submit


def register(sessions, tenant, label):
    registration = router.DeviceRegistration(token=label * 20, binding=uuid4())
    with sessions() as db:
        router.subscribe(registration, db.get(AdminUser, tenant), db)
    return registration


def test_push_uses_order_commit_and_replays_only_one_alert(sessions, monkeypatch):
    monkeypatch.setenv("MANAGEMENT_PUSH_ENABLED", "true")
    monkeypatch.setattr(worker, "send_whatsapp_message", fake_sender([]))
    valid = register(sessions, 1, "a")
    register(sessions, 2, "b")
    revoked = register(sessions, 1, "c")
    with sessions() as db, db.begin():
        db.get(ManagementPushDevice, revoked.token).credential_version = -1
    sent = []
    monkeypatch.setattr(management_push, "send_order_alert", lambda device, _: sent.append(device.token) or True)
    submit(sessions)
    submit(sessions)
    assert worker.run_cycle(sessions, clock=lambda: NOW)["done"] == 2
    assert sent == [valid.token]
    assert worker.run_cycle(sessions, clock=lambda: NOW)["done"] == 0


def test_push_retry_skips_success_and_removes_unregistered_device(sessions, monkeypatch):
    monkeypatch.setenv("MANAGEMENT_PUSH_ENABLED", "true")
    monkeypatch.setattr(worker, "send_whatsapp_message", fake_sender([]))
    good = register(sessions, 1, "d")
    missing = register(sessions, 1, "e")
    sent = []

    def send(device, _):
        sent.append(device.token)
        if device.token == missing.token:
            if sent.count(missing.token) == 1:
                raise RuntimeError("provider unavailable")
            return False
        return True

    monkeypatch.setattr(management_push, "send_order_alert", send)
    submit(sessions)
    assert worker.run_cycle(sessions, clock=lambda: NOW)["retry"] == 1
    assert worker.run_cycle(sessions, clock=lambda: NOW + timedelta(minutes=1))["done"] == 1
    assert sent.count(good.token) == 1 and sent.count(missing.token) == 2
    with sessions() as db:
        assert db.get(ManagementPushDevice, missing.token) is None


def test_unsubscribe_cannot_remove_another_tenants_device(sessions, monkeypatch):
    monkeypatch.setenv("MANAGEMENT_PUSH_ENABLED", "true")
    registration = register(sessions, 1, "f")
    with sessions() as db:
        router.unsubscribe(registration, db.get(AdminUser, 2), db)
        assert db.get(ManagementPushDevice, registration.token).tenant_id == 1
        router.unsubscribe(registration, db.get(AdminUser, 1), db)
        assert db.get(ManagementPushDevice, registration.token) is None


@pytest.mark.parametrize("enabled", [True, False])
def test_rollout_defaults_off_and_stale_alert_is_discarded(sessions, monkeypatch, enabled):
    monkeypatch.delenv("MANAGEMENT_PUSH_ENABLED", raising=False)
    if enabled:
        monkeypatch.setenv("MANAGEMENT_PUSH_ENABLED", "true")
        register(sessions, 1, "g")
    submit(sessions)
    with sessions() as db:
        assert db.query(OrderOutbox).filter_by(effect=management_push.EFFECT).count() == int(enabled)
    monkeypatch.setattr(worker, "send_whatsapp_message", fake_sender([]))

    def unexpected_send(*_):
        pytest.fail("Stale notifications must not call FCM")

    monkeypatch.setattr(management_push, "send_order_alert", unexpected_send)
    assert worker.run_cycle(sessions, clock=lambda: NOW + timedelta(minutes=6))["done"] == 1 + int(enabled)
