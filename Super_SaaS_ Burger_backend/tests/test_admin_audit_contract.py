"""Intentional API contract for human and automatic administrative audit actors."""
import json
from pathlib import Path

from fastapi import FastAPI
from pydantic import ValidationError
import pytest

from app.routers.admin_audit import AdminAuditRead, router

SNAPSHOT = Path(__file__).resolve().parents[1] / "contracts" / "openapi_snapshot.json"


def audit_payload(**changes):
    payload = dict(id=1, tenant_id=1, user_id=7, user_name="Admin", user_email="admin@example.test",
                   action="legacy.action", entity_type="subscription", entity_id=1,
                   meta=None, created_at="2026-10-06T12:00:00Z")
    payload.update(changes)
    return payload


def test_audit_openapi_contract_declares_required_nullable_user_and_explicit_actor():
    app = FastAPI()
    app.include_router(router)
    schema = app.openapi()["components"]["schemas"]["AdminAuditRead"]
    assert "user_id" in schema["required"]
    assert schema["properties"]["user_id"]["anyOf"] == [{"type": "integer"}, {"type": "null"}]
    assert schema["properties"]["actor_type"]["type"] == "string"
    assert schema["properties"]["actor_type"]["default"] == "user"
    assert "actor_type" not in schema["required"]
    approved = json.loads(SNAPSHOT.read_text())["components"]["schemas"]["AdminAuditRead"]
    assert schema == approved


@pytest.mark.parametrize("actor_type,user_id", [("user", 7), ("system", None), ("provider", None)])
def test_audit_response_serializes_human_and_automatic_identity(actor_type, user_id):
    response = AdminAuditRead.model_validate(audit_payload(actor_type=actor_type, user_id=user_id))
    serialized = response.model_dump(mode="json")
    assert "user_id" in serialized
    assert serialized["user_id"] == user_id
    assert serialized["actor_type"] == actor_type


def test_nullable_user_id_is_still_required_in_the_response_contract():
    payload = audit_payload(actor_type="system")
    del payload["user_id"]
    with pytest.raises(ValidationError) as error:
        AdminAuditRead.model_validate(payload)
    assert any(item["loc"] == ("user_id",) and item["type"] == "missing" for item in error.value.errors())


def test_previous_human_audit_payload_remains_valid():
    response = AdminAuditRead.model_validate(audit_payload())
    assert response.user_id == 7
    assert response.actor_type == "user"
