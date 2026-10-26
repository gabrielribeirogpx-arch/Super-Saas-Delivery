from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.models.order import Order
from app.services import event_handlers, order_events, whatsapp_outbound
from app.services.order_events import build_order_payload
from app.services.whatsapp_templates import TEMPLATES
from app.whatsapp.service import WhatsAppService


TOKEN = "safe-public-token-not-an-order-id"
PUBLIC_URL = f"https://fomizero.com.br/pedido/{TOKEN}"


def _order(status: str, **overrides) -> Order:
    values = {
        "id": 987654,
        "daily_order_number": 42,
        "tenant_id": 1,
        "status": status,
        "cliente_nome": "Ana",
        "cliente_telefone": "5511999999999",
        "total_cents": 2500,
        "tipo_entrega": "ENTREGA",
        "tracking_token": TOKEN,
        "tracking_expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        "tracking_revoked": False,
    }
    values.update(overrides)
    return Order(**values)


@pytest.mark.parametrize("status", ["OUT_FOR_DELIVERY", "SAIU", "SAIU_PARA_ENTREGA"])
def test_out_for_delivery_payload_uses_tracking_token_not_order_id(monkeypatch, status):
    monkeypatch.setattr(order_events, "PUBLIC_BASE_DOMAIN", "fomizero.com.br")

    payload = build_order_payload(_order(status))

    assert payload["tracking_url"] == PUBLIC_URL
    assert str(payload["order_id"]) not in payload["tracking_url"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"tracking_token": None},
        {"tracking_token": "  "},
        {"tracking_revoked": True},
        {"tracking_expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)},
    ],
)
def test_invalid_tracking_does_not_generate_a_broken_url(monkeypatch, overrides):
    monkeypatch.setattr(order_events, "PUBLIC_BASE_DOMAIN", "fomizero.com.br")

    payload = build_order_payload(_order("OUT_FOR_DELIVERY", **overrides))

    assert "tracking_url" not in payload


@pytest.mark.parametrize("status", ["RECEBIDO", "EM_PREPARO", "PRONTO", "ENTREGUE", "DELIVERED"])
def test_unrelated_status_events_do_not_receive_tracking_url(monkeypatch, status):
    monkeypatch.setattr(order_events, "PUBLIC_BASE_DOMAIN", "fomizero.com.br")

    assert "tracking_url" not in build_order_payload(_order(status))


def test_out_for_delivery_template_renders_link_and_has_safe_fallback():
    variables = {
        "customer_name": "Ana",
        "order_number": 42,
        "estimated_time": "30 min",
        "tracking_url": PUBLIC_URL,
    }

    rendered = whatsapp_outbound._render_template("order_out_for_delivery", variables)
    fallback = whatsapp_outbound._render_template(
        "order_out_for_delivery", {**variables, "tracking_url": ""}
    )

    assert f"Acompanhe seu entregador em tempo real: {PUBLIC_URL}" in rendered
    assert "None" not in fallback
    assert "/pedido/null" not in fallback
    assert "Acompanhe seu entregador" not in fallback


def test_other_whatsapp_templates_remain_unchanged():
    assert TEMPLATES["order_confirmed"] == (
        "Olá {customer_name}! ✅ Seu pedido #{order_number} foi confirmado. "
        "Total: {order_total}. Tempo estimado: {estimated_time}."
    )
    assert TEMPLATES["order_in_preparation"] == (
        "Olá {customer_name}! 👨‍🍳 Seu pedido #{order_number} está em preparo. "
        "Tempo estimado: {estimated_time}."
    )
    assert TEMPLATES["order_ready"] == (
        "Olá {customer_name}! 🍔✅ Seu pedido #{order_number} está pronto. "
        "Total: {order_total}."
    )
    assert TEMPLATES["order_delivered"] == (
        "Olá {customer_name}! 📦 Pedido #{order_number} entregue. "
        "Total: {order_total}. Obrigado pela preferência!"
    )


def test_handler_only_passes_tracking_url_to_out_for_delivery(monkeypatch):
    sent = []
    fake_db = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(event_handlers, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(event_handlers, "send_whatsapp_message", lambda *args, **kwargs: sent.append(kwargs))
    base_payload = {
        "tenant_id": 1,
        "customer_phone": "5511999999999",
        "customer_name": "Ana",
        "order_number": 42,
        "order_id": 987654,
        "estimated_time": "30 min",
        "tracking_url": PUBLIC_URL,
    }

    event_handlers.handle_order_status_changed({**base_payload, "status": "OUT_FOR_DELIVERY"})
    event_handlers.handle_order_status_changed({**base_payload, "status": "PRONTO"})

    assert sent[0]["variables"]["tracking_url"] == PUBLIC_URL
    assert "tracking_url" not in sent[1]["variables"]
    assert "tracking_token" not in sent[0]["variables"]
    assert "order_id" not in sent[0]["variables"]


def test_complete_tracking_token_is_redacted_from_outbound_log(monkeypatch, caplog):
    captured = {}

    class FakeService:
        def send_template(self, *args, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace()

    fake_db = SimpleNamespace(commit=lambda: None)
    monkeypatch.setattr(whatsapp_outbound, "is_customer_opted_in", lambda *_args: True)
    monkeypatch.setattr(whatsapp_outbound, "WhatsAppService", FakeService)
    monkeypatch.setattr(whatsapp_outbound, "log_admin_action", lambda *_args, **_kwargs: None)

    with caplog.at_level(logging.INFO, logger="app.services.whatsapp_outbound"):
        whatsapp_outbound.send_whatsapp_message(
            fake_db,
            tenant_id=1,
            phone="5511999999999",
            template="order_out_for_delivery",
            variables={
                "customer_name": "Ana",
                "order_number": 42,
                "estimated_time": "30 min",
                "tracking_url": PUBLIC_URL,
            },
            order_id=987654,
        )

    assert TOKEN not in caplog.text
    assert ":token-" in caplog.text
    assert PUBLIC_URL in captured["variables"]["rendered_text"]


def test_template_deduplication_still_short_circuits_provider(monkeypatch):
    service = WhatsAppService()
    db = SimpleNamespace()
    monkeypatch.setattr(service, "_is_duplicate_template", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        service._mock_provider,
        "send_template",
        lambda *_args, **_kwargs: pytest.fail("duplicate reached provider"),
    )

    result = service.send_template(
        db,
        tenant_id=1,
        to_phone="5511999999999",
        template_name="order_out_for_delivery",
        variables={"tracking_url": PUBLIC_URL},
        order_id=987654,
        status_stage="order_out_for_delivery",
    )

    assert result is None


def test_internal_deduplication_fields_are_not_sent_as_template_variables(monkeypatch):
    service = WhatsAppService()
    received = {}
    monkeypatch.setattr(service, "_is_duplicate_template", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(service, "get_config", lambda *_args: None)

    def capture(*_args, **kwargs):
        received.update(kwargs)
        return SimpleNamespace(status="sent")

    monkeypatch.setattr(service._mock_provider, "send_template", capture)

    service.send_template(
        SimpleNamespace(),
        tenant_id=1,
        to_phone="5511999999999",
        template_name="order_out_for_delivery",
        variables={"tracking_url": PUBLIC_URL},
        order_id=987654,
        status_stage="order_out_for_delivery",
    )

    assert received["variables"] == {"tracking_url": PUBLIC_URL}
    assert received["context"] == {
        "order_id": 987654,
        "status_stage": "order_out_for_delivery",
    }
