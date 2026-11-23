"""Turn a fresh, customer-confirmed Wazza quote into an official checkout."""

from datetime import datetime, timezone
import hmac
import json
import re
import time
from typing import Any

from anyio import from_thread
from fastapi import HTTPException
from pydantic import Field
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core import config
from app.models.order_durability import OrderSubmission
from app.models.tenant import Tenant
from app.models.wazza_mcp import WazzaOrderDraft
from app.routers import public_menu as checkout
from app.services.order_idempotency import Attempt
from app.services.wazza_mcp_errors import McpToolError
from app.services.wazza_mcp_identity import VerifiedCustomerIdentity
from app.services.wazza_mcp_order_drafts import (
    DraftMutationArguments, _hash, _mutation_fingerprint, owned_drafts, quote_draft,
    require_fresh_draft,
)


QUOTE_TTL_SECONDS = 300


class DraftConfirmArguments(DraftMutationArguments):
    confirmation_token: str = Field(pattern=r"^[0-9]{1,12}\.[a-f0-9]{64}$")


def confirmation_available() -> bool:
    return bool(config.WAZZA_MCP_ORDER_CONFIRM_ENABLED and config.JWT_SECRET_KEY)


def _signature(
    draft: WazzaOrderDraft, summary: dict[str, Any], identity: VerifiedCustomerIdentity, expiry: int,
) -> str:
    message = json.dumps(
        ["fomizero-wazza-order-confirm-v1", draft.tenant_id, draft.owner_hash,
         identity.conversation_id, expiry, summary],
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hmac.new(config.JWT_SECRET_KEY.encode(), message.encode(), "sha256").hexdigest()


def issue_quote_token(
    draft: WazzaOrderDraft, summary: dict[str, Any], identity: VerifiedCustomerIdentity,
) -> dict[str, str]:
    expires = min(int(require_fresh_draft(draft).timestamp()), int(time.time()) + QUOTE_TTL_SECONDS)
    return {
        "confirmation_token": f"{expires}.{_signature(draft, summary, identity, expires)}",
        "confirmation_expires_at": datetime.fromtimestamp(expires, timezone.utc).isoformat(),
    }


def _validate_token(
    draft: WazzaOrderDraft, summary: dict[str, Any], identity: VerifiedCustomerIdentity, token: str,
) -> None:
    timestamp, _, signature = token.partition(".")
    expiry = int(timestamp)
    if time.time() >= expiry:
        raise McpToolError("confirmation_expired", "Solicite novo orçamento e nova confirmação.")
    if not summary["ready_to_confirm"] or not hmac.compare_digest(
        signature, _signature(draft, summary, identity, expiry),
    ):
        raise McpToolError("quote_changed", "Solicite novo orçamento e nova confirmação.")


def _checkout_payload(summary: dict[str, Any], identity: VerifiedCustomerIdentity) -> checkout.PublicOrderPayload:
    fulfillment = summary["fulfillment"]
    address = fulfillment.get("address") or {}
    if fulfillment["type"] == "delivery" and (
        not re.fullmatch(r"\d{5}-?\d{3}", address.get("zip") or "", flags=re.ASCII)
        or not re.fullmatch(r"[A-Za-z]{2}", address.get("state") or "")
        or any(not address.get(key) for key in ("street", "number", "neighborhood", "city"))
    ):
        raise McpToolError("invalid_delivery_address", "Endereço de entrega inválido.")
    payment = summary["payment"]
    if payment["method"] not in {"pix", "cash", "credit_card", "debit_card"}:
        raise McpToolError("invalid_payment", "Forma de pagamento inválida.")
    change = payment.get("change_for_cents")
    if change and (payment["method"] != "cash" or change < summary["total_cents"]):
        raise McpToolError("invalid_payment", "Valor para troco inválido.")
    return checkout.PublicOrderPayload(
        customer_phone=identity.phone,
        order_type=fulfillment["type"],
        delivery_type="ENTREGA" if fulfillment["type"] == "delivery" else "RETIRADA",
        delivery_address=address,
        **{key: address.get(key) or "" for key in
           ("street", "number", "neighborhood", "city", "state", "complement", "reference")},
        payment_method=payment["method"],
        payment_change_for=f"{change // 100}.{change % 100:02d}" if change else "",
        notes="\n".join(f"{line['name']}: {line['notes']}" for line in summary["items"] if line["notes"]),
        items=[
            checkout.PublicOrderItem(
                item_id=line["item_id"], quantity=line["quantity"],
                selected_modifiers=[
                    checkout.PublicSelectedModifier(group_id=entry["group_id"], option_id=entry["option_id"])
                    for entry in line["modifiers"]
                ],
            )
            for line in summary["items"]
        ],
    )


def _check_checkout_quote(
    summary: dict[str, Any], items: list[dict], fee: int, discount: int, total: int,
) -> None:
    if (fee, discount, total) != (
        summary["delivery_fee_cents"], summary["discount_cents"], summary["total_cents"],
    ) or len(items) != len(summary["items"]):
        raise McpToolError("quote_changed", "Solicite novo orçamento e nova confirmação.")
    for item, quoted in zip(items, summary["items"]):
        if (
            item["menu_item_id"] != quoted["item_id"]
            or item["name"] != quoted["name"]
            or item["quantity"] != quoted["quantity"]
            or item["unit_price_cents"] != quoted["base_price_cents"]
            or [
                {key: value for key, value in modifier.items() if key != "name"}
                for modifier in item["modifiers"]
            ] != quoted["modifiers"]
        ):
            raise McpToolError("quote_changed", "Solicite novo orçamento e nova confirmação.")


def order_draft_confirm(
    db: Session, tenant_id: int, args: DraftConfirmArguments, identity: VerifiedCustomerIdentity,
) -> dict[str, Any]:
    # Resolve ownership before looking up any receipt. Geocoding stays outside the
    # store lock, and only a verified, unchanged quote can use those coordinates.
    drafts = owned_drafts(db, tenant_id, identity)
    draft_query = drafts.filter(WazzaOrderDraft.public_id == args.draft_id)
    draft = draft_query.first()
    if draft is None:
        raise McpToolError("draft_not_found", "Rascunho não encontrado.")
    key_hash, request_hash = _mutation_fingerprint(args)
    attempt = Attempt(tenant_id, _hash(f"wazza-confirm:{draft.owner_hash}:{key_hash}"), request_hash)
    coordinates = (None, None)
    if draft.status == "active" and (draft.fulfillment_json or {}).get("type") == "delivery":
        try:
            summary = quote_draft(db, tenant_id, draft)
            _validate_token(draft, summary, identity, args.confirmation_token)
            payload = _checkout_payload(summary, identity)
            checkout._validate_delivery_zip(payload, payload.delivery_address)
            checkout.require_feature(db, tenant_id, "orders_monthly")
        except (McpToolError, HTTPException):
            # The draft may have been committed by another worker since the first
            # read. Recheck under lock so an exact replay wins over quote expiry.
            pass
        else:
            try:
                coordinates = from_thread.run(checkout.geocode_address, checkout.build_full_address(payload))
            except Exception:
                checkout.logger.warning("wazza_geocoding_failed_before_order")

    if db.get_bind().dialect.name == "sqlite":
        db.execute(update(Tenant).where(Tenant.id == tenant_id).values(id=Tenant.id))
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).populate_existing().with_for_update(key_share=True).one()
    draft = draft_query.populate_existing().with_for_update().one_or_none()
    if draft is None:
        raise McpToolError("draft_not_found", "Rascunho não encontrado.")
    previous = drafts.filter(WazzaOrderDraft.confirmation_key_hash == attempt.key_hash).one_or_none()
    if previous is not None:
        if not hmac.compare_digest(previous.confirmation_request_hash, request_hash):
            raise McpToolError("idempotency_conflict", "Chave reutilizada com outros dados.")
        return {"draft_id": previous.public_id, "order_id": previous.confirmed_order_id}
    if draft.status == "confirmed":
        raise McpToolError("draft_already_confirmed", "Rascunho já confirmado.")
    if draft.status != "active":
        raise McpToolError("draft_expired", "Rascunho expirado.")

    summary = quote_draft(db, tenant_id, draft)
    _validate_token(draft, summary, identity, args.confirmation_token)
    payload = _checkout_payload(summary, identity)

    def check_quote(items, fee, discount, total):
        _check_checkout_quote(summary, items, fee, discount, total)
        require_fresh_draft(draft)
        _validate_token(draft, summary, identity, args.confirmation_token)

    checkout._persist_order_transaction(
        db, tenant, payload, attempt=attempt, coordinates=coordinates, wazza_quote_check=check_quote,
    )
    receipt = db.get(OrderSubmission, (tenant_id, attempt.key_hash))
    draft.confirmed_order_id = receipt.order_id
    draft.confirmed_at = datetime.now(timezone.utc)
    draft.confirmation_key_hash = attempt.key_hash
    draft.confirmation_request_hash = request_hash
    draft.status = "confirmed"
    return {"draft_id": draft.public_id, "order_id": draft.confirmed_order_id}
