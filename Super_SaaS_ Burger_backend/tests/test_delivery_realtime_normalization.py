import json

from app.realtime.delivery_envelope import DELIVERY_SCHEMA_VERSION, build_delivery_envelope, parse_delivery_envelope
from app.realtime.publisher import (
    delivery_assignment_channel,
    delivery_location_channel,
    delivery_status_channel,
    publish_order_tracking_eta_event,
)


def test_delivery_envelope_contract_has_required_fields():
    envelope = build_delivery_envelope(
        event_type="delivery.location",
        tenant_id=5,
        order_id=22,
        delivery_user_id=99,
        payload={"lat": -23.5, "lng": -46.6},
    )

    assert envelope == {
        "type": "delivery.location",
        "schema_version": DELIVERY_SCHEMA_VERSION,
        "tenant_id": 5,
        "order_id": 22,
        "delivery_user_id": 99,
        "payload": {"lat": -23.5, "lng": -46.6},
        "ts": envelope["ts"],
    }
    assert isinstance(envelope["ts"], str)


def test_delivery_channels_use_normalized_naming():
    assert delivery_status_channel(3) == "tenant:3:delivery:status"
    assert delivery_location_channel(3) == "tenant:3:delivery:location"
    assert delivery_assignment_channel(3) == "tenant:3:delivery:assignment"


def test_parse_delivery_envelope_validates_schema_and_tenant_isolation():
    envelope = build_delivery_envelope(
        event_type="delivery.assignment",
        tenant_id=7,
        order_id=41,
        delivery_user_id=11,
        payload={"status": "OUT_FOR_DELIVERY"},
    )

    payload_text = json.dumps(envelope)

    assert parse_delivery_envelope(payload_text, expected_tenant_id=7) == envelope
    assert parse_delivery_envelope(payload_text, expected_tenant_id=8) is None



def test_parse_delivery_envelope_ignores_malformed_messages():
    assert parse_delivery_envelope("not-json", expected_tenant_id=1) is None
    assert parse_delivery_envelope(json.dumps({"tenant_id": 1}), expected_tenant_id=1) is None

    wrong_schema = {
        "type": "delivery.status",
        "schema_version": 2,
        "tenant_id": 1,
        "order_id": None,
        "delivery_user_id": 5,
        "payload": {"status": "online"},
        "ts": "2025-01-01T00:00:00+00:00",
    }
    assert parse_delivery_envelope(json.dumps(wrong_schema), expected_tenant_id=1) is None


def test_publish_order_tracking_eta_event_uses_order_channel_payload(monkeypatch):
    published = {}

    def _fake_publish(channel, payload):
        published["channel"] = channel
        published["payload"] = payload
        return 1

    monkeypatch.setattr("app.realtime.publisher._publish", _fake_publish)

    response = publish_order_tracking_eta_event(
        tenant_id=9,
        order_id=44,
        lat=-21.12,
        lng=-48.15,
        remaining_seconds=480,
        status="ON_TIME",
        schema_version=1,
    )

    assert response == 1
    assert published["channel"] == "tenant:9:order:44:tracking"
    assert published["payload"] == {
        "order_id": 44,
        "lat": -21.12,
        "lng": -48.15,
        "remaining_seconds": 480,
        "status": "ON_TIME",
        "schema_version": 1,
    }
