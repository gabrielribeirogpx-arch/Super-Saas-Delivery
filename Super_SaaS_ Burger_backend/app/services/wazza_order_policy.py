"""Pure policy for customer-initiated order mutations through Wazza.

The transport and the language model never decide whether an order may be
changed.  Keeping this decision in Fomizero makes it reusable by MCP, REST and
future channels and gives tests one authoritative policy to protect.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.order_statuses import canonical_status


class CustomerOrderAction(str, Enum):
    EDIT = "edit"
    CANCEL = "cancel"


class MutationDisposition(str, Enum):
    CUSTOMER_CONFIRMATION = "customer_confirmation"
    HUMAN_APPROVAL = "human_approval"
    DENIED = "denied"


@dataclass(frozen=True)
class MutationDecision:
    disposition: MutationDisposition
    reason: str


_RECEIVED = {"RECEBIDO"}
_IN_PRODUCTION = {"EM_PREPARO"}
_TERMINAL_OR_FULFILMENT = {
    "PRONTO",
    "DRIVER_ASSIGNED",
    "SAIU_PARA_ENTREGA",
    "ENTREGUE",
    "CANCELADO",
    "CANCELLED",
    "CANCELED",
}


def decide_customer_mutation(status: str | None, action: CustomerOrderAction) -> MutationDecision:
    """Return the minimum authorization required for a customer mutation."""

    current = canonical_status(status)
    if current in _RECEIVED:
        return MutationDecision(
            MutationDisposition.CUSTOMER_CONFIRMATION,
            f"order_{action.value}_requires_explicit_customer_confirmation",
        )
    if current in _IN_PRODUCTION:
        return MutationDecision(
            MutationDisposition.HUMAN_APPROVAL,
            f"order_{action.value}_requires_restaurant_approval",
        )
    if current in _TERMINAL_OR_FULFILMENT:
        return MutationDecision(
            MutationDisposition.DENIED,
            f"order_{action.value}_not_allowed_in_{current.lower()}",
        )
    return MutationDecision(
        MutationDisposition.DENIED,
        "order_status_not_supported_for_customer_mutation",
    )
