from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from app.services.wazza_order_policy import (
    CustomerOrderAction,
    MutationDisposition,
    decide_customer_mutation,
)


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "contracts" / "wazza_mcp_v1.json"


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_wazza_is_fail_closed_by_default(monkeypatch):
    monkeypatch.delenv("WAZZA_MCP_ENABLED", raising=False)
    from app.core import config

    reloaded = importlib.reload(config)
    assert reloaded.WAZZA_MCP_ENABLED is False


def test_contract_never_accepts_tenant_or_phone_as_tool_arguments():
    identity = _contract()["identity"]
    assert identity["tenant_source"] == "authenticated_connection"
    assert identity["customer_source"] == "signed_whatsapp_context"
    assert {"tenant_id", "customer_phone", "customer_phone_e164"}.issubset(
        identity["forbidden_tool_arguments"]
    )


def test_contract_keeps_every_tool_disabled_until_its_rollout_phase():
    contract = _contract()
    assert contract["default_enabled"] is False
    assert contract["tools"]
    assert all(tool["enabled"] is False for tool in contract["tools"])
    assert len({tool["name"] for tool in contract["tools"]}) == len(contract["tools"])


def test_contract_marks_only_tenant_safe_menu_reads_as_implemented():
    implemented = {tool["name"] for tool in _contract()["tools"] if tool.get("implemented")}
    assert implemented == {
        "restaurant_get_status",
        "menu_list_categories",
        "menu_search_items",
        "menu_get_item",
    }


def test_contract_forbids_model_authority_over_money_and_status():
    requirements = _contract()["mutation_requirements"]
    assert requirements["idempotency_key"] is True
    assert requirements["fresh_server_side_recalculation"] is True
    assert requirements["explicit_customer_confirmation"] is True
    assert requirements["model_supplied_prices_are_accepted"] is False
    assert requirements["model_may_mark_payment_as_paid"] is False
    assert requirements["model_may_change_order_status_directly"] is False


def test_contract_requires_tenant_bound_revocable_credentials_and_minimal_audit():
    authentication = _contract()["authentication"]
    assert authentication["credential_tenant_bound"] is True
    assert authentication["raw_token_persisted"] is False
    assert authentication["wildcard_scopes_allowed"] is False
    assert authentication["credentials_can_expire"] is True
    assert authentication["credentials_can_be_revoked"] is True
    assert authentication["audit_argument_values_persisted"] is False


@pytest.mark.parametrize("action", list(CustomerOrderAction))
def test_received_order_requires_explicit_customer_confirmation(action):
    decision = decide_customer_mutation("RECEBIDO", action)
    assert decision.disposition is MutationDisposition.CUSTOMER_CONFIRMATION


@pytest.mark.parametrize("status", ["EM_PREPARO", "PREPARO", "PREPARANDO"])
@pytest.mark.parametrize("action", list(CustomerOrderAction))
def test_order_in_production_requires_human_approval(status, action):
    decision = decide_customer_mutation(status, action)
    assert decision.disposition is MutationDisposition.HUMAN_APPROVAL


@pytest.mark.parametrize(
    "status",
    ["PRONTO", "READY", "DRIVER_ASSIGNED", "SAIU_PARA_ENTREGA", "OUT_FOR_DELIVERY", "ENTREGUE", "DELIVERED", "CANCELADO"],
)
@pytest.mark.parametrize("action", list(CustomerOrderAction))
def test_fulfilment_and_terminal_orders_cannot_be_mutated_by_customer(status, action):
    decision = decide_customer_mutation(status, action)
    assert decision.disposition is MutationDisposition.DENIED


def test_unknown_status_fails_closed():
    decision = decide_customer_mutation("UNRECOGNIZED", CustomerOrderAction.CANCEL)
    assert decision.disposition is MutationDisposition.DENIED
