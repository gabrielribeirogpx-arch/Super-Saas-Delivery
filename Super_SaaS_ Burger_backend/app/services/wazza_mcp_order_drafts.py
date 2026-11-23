"""Safe, isolated Wazza carts. These handlers never create an Order."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import secrets
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.menu_item import MenuItem
from app.models.modifier_group import ModifierGroup
from app.models.modifier_option import ModifierOption
from app.models.tenant import Tenant
from app.models.wazza_mcp import WazzaOrderDraft
from app.services.wazza_mcp_errors import McpToolError
from app.services.wazza_mcp_identity import VerifiedCustomerIdentity


DRAFT_TTL = timedelta(hours=2)


class StrictArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DraftCreateArguments(StrictArguments):
    idempotency_key: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class DraftRefArguments(StrictArguments):
    draft_id: str = Field(min_length=32, max_length=32, pattern=r"^[a-f0-9]{32}$")


class DraftMutationArguments(DraftRefArguments):
    idempotency_key: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class DraftAddItemArguments(DraftMutationArguments):
    item_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=50)
    modifier_option_ids: list[int] = Field(default_factory=list, max_length=30)
    notes: str | None = Field(default=None, max_length=300)


class DraftUpdateItemArguments(DraftMutationArguments):
    line_id: str = Field(min_length=16, max_length=16, pattern=r"^[a-f0-9]{16}$")
    quantity: int | None = Field(default=None, ge=1, le=50)
    modifier_option_ids: list[int] | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def at_least_one_change(self):
        if self.quantity is None and self.modifier_option_ids is None and self.notes is None:
            raise ValueError("at least one item change is required")
        return self


class DraftRemoveItemArguments(DraftMutationArguments):
    line_id: str = Field(min_length=16, max_length=16, pattern=r"^[a-f0-9]{16}$")


class DeliveryAddress(StrictArguments):
    zip: str = Field(min_length=8, max_length=20)
    street: str = Field(min_length=1, max_length=150)
    number: str = Field(min_length=1, max_length=20)
    complement: str | None = Field(default=None, max_length=150)
    neighborhood: str = Field(min_length=1, max_length=100)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=2, max_length=2)
    reference: str | None = Field(default=None, max_length=150)


class DraftDeliveryArguments(DraftMutationArguments):
    fulfillment_type: Literal["delivery", "pickup"]
    address: DeliveryAddress | None = None

    @model_validator(mode="after")
    def delivery_requires_address(self):
        if self.fulfillment_type == "delivery" and self.address is None:
            raise ValueError("delivery address is required")
        if self.fulfillment_type == "pickup" and self.address is not None:
            raise ValueError("pickup cannot include an address")
        return self


class DraftPaymentArguments(DraftMutationArguments):
    payment_method: Literal["pix", "cash", "credit_card", "debit_card"]
    change_for_cents: int | None = Field(default=None, ge=0, le=10_000_000)

    @model_validator(mode="after")
    def change_only_for_cash(self):
        if self.payment_method != "cash" and self.change_for_cents is not None:
            raise ValueError("change is only valid for cash")
        return self


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _owner(identity: VerifiedCustomerIdentity) -> str:
    digits = "".join(character for character in identity.phone if character.isdigit())
    return _hash(digits)


def _mutation_fingerprint(args: DraftMutationArguments) -> tuple[str, str]:
    key_hash = _hash(args.idempotency_key)
    payload = args.model_dump(mode="json", exclude={"idempotency_key"})
    payload_hash = _hash(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return key_hash, payload_hash


def _is_replay(draft: WazzaOrderDraft, args: DraftMutationArguments) -> bool:
    key_hash, payload_hash = _mutation_fingerprint(args)
    previous = dict(draft.mutation_keys_json or {}).get(key_hash)
    if previous is not None and previous != payload_hash:
        raise McpToolError("idempotency_conflict", "Chave de idempotência reutilizada com outros dados.")
    return previous == payload_hash


def _record_mutation(draft: WazzaOrderDraft, args: DraftMutationArguments) -> None:
    key_hash, payload_hash = _mutation_fingerprint(args)
    entries = dict(draft.mutation_keys_json or {})
    entries[key_hash] = payload_hash
    draft.mutation_keys_json = dict(list(entries.items())[-100:])


def owned_drafts(db: Session, tenant_id: int, identity: VerifiedCustomerIdentity):
    return db.query(WazzaOrderDraft).filter(
        WazzaOrderDraft.tenant_id == tenant_id,
        WazzaOrderDraft.owner_hash == _owner(identity),
    )


def require_fresh_draft(draft: WazzaOrderDraft) -> datetime:
    expires_at = draft.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= _now():
        raise McpToolError("draft_expired", "Rascunho expirado.")
    return expires_at


def _get_draft(
    db: Session, tenant_id: int, identity: VerifiedCustomerIdentity, public_id: str,
    *, for_write: bool = False,
) -> WazzaOrderDraft:
    query = owned_drafts(db, tenant_id, identity).filter(
        WazzaOrderDraft.public_id == public_id, WazzaOrderDraft.status == "active",
    )
    if for_write:
        if db.get_bind().dialect.name == "sqlite":
            # Acquire SQLite's writer lock before reading the version to mutate.
            db.execute(update(WazzaOrderDraft).where(
                WazzaOrderDraft.tenant_id == tenant_id,
                WazzaOrderDraft.owner_hash == _owner(identity),
                WazzaOrderDraft.public_id == public_id,
                WazzaOrderDraft.status == "active",
            ).values(version=WazzaOrderDraft.version))
        query = query.with_for_update()
    draft = query.first()
    if draft is None:
        raise McpToolError("draft_not_found", "Rascunho não encontrado.")
    try:
        require_fresh_draft(draft)
    except McpToolError:
        if for_write:
            draft.status = "expired"
        raise
    return draft


def _money_cents(value: Decimal | float | int | None) -> int:
    return int(round(float(value or 0) * 100))


def _price_line(db: Session, tenant_id: int, item_id: int, quantity: int, option_ids: list[int], notes: str | None, *, line_id: str | None = None) -> dict[str, Any]:
    if len(option_ids) != len(set(option_ids)):
        raise McpToolError("invalid_modifiers", "Adicionais duplicados.")
    item = db.query(MenuItem).filter(MenuItem.id == item_id, MenuItem.tenant_id == tenant_id, MenuItem.active.is_(True)).first()
    if item is None:
        raise McpToolError("item_not_found", "Item não encontrado ou indisponível.")
    groups = db.query(ModifierGroup).filter(ModifierGroup.tenant_id == tenant_id, ModifierGroup.product_id == item.id, ModifierGroup.active.is_(True)).all()
    groups_by_id = {int(group.id): group for group in groups}
    options = (
        db.query(ModifierOption)
        .filter(ModifierOption.id.in_(option_ids), ModifierOption.is_active.is_(True))
        .all()
        if option_ids
        else []
    )
    if len(options) != len(option_ids):
        raise McpToolError("invalid_modifiers", "Adicional inválido ou indisponível.")
    selected_by_group: dict[int, list[ModifierOption]] = {}
    for option in options:
        group = groups_by_id.get(int(option.group_id))
        if group is None:
            raise McpToolError("invalid_modifiers", "Adicional não pertence ao item.")
        selected_by_group.setdefault(int(group.id), []).append(option)
    for group in groups:
        count = len(selected_by_group.get(int(group.id), []))
        if count < int(group.min_selection or (1 if group.required else 0)):
            raise McpToolError("required_modifier_missing", f"Seleção obrigatória ausente: {group.name}.")
        if count > int(group.max_selection or 1):
            raise McpToolError("modifier_limit_exceeded", f"Limite excedido: {group.name}.")
    option_map = {int(option.id): option for option in options}
    modifiers = []
    modifiers_cents = 0
    for option_id in option_ids:
        option = option_map[option_id]
        group = groups_by_id[int(option.group_id)]
        price_cents = _money_cents(option.price_delta)
        modifiers_cents += price_cents
        modifiers.append({"group_id": int(group.id), "group_name": group.name, "option_id": int(option.id), "option_name": option.name, "price_cents": price_cents})
    unit_cents = int(item.price_cents) + modifiers_cents
    return {
        "line_id": line_id or secrets.token_hex(8),
        "item_id": int(item.id),
        "name": item.name,
        "quantity": quantity,
        "base_price_cents": int(item.price_cents),
        "modifiers": modifiers,
        "unit_price_cents": unit_cents,
        "subtotal_cents": unit_cents * quantity,
        "notes": notes or None,
    }


def _summary(draft: WazzaOrderDraft, *, items_override: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    items = list(draft.items_json or []) if items_override is None else items_override
    subtotal = sum(int(item.get("subtotal_cents") or 0) for item in items)
    fulfillment = draft.fulfillment_json or None
    delivery = int(fulfillment.get("delivery_fee_cents") or 0) if fulfillment else 0
    return {
        "draft_id": draft.public_id,
        "version": int(draft.version),
        "status": draft.status,
        "items": items,
        "fulfillment": fulfillment,
        "payment": draft.payment_json or None,
        "subtotal_cents": subtotal,
        "delivery_fee_cents": delivery,
        "total_cents": subtotal + delivery,
        "expires_at": draft.expires_at.isoformat(),
    }


def _touch(draft: WazzaOrderDraft) -> None:
    draft.version = int(draft.version) + 1
    draft.updated_at = _now()
    draft.expires_at = _now() + DRAFT_TTL


def order_draft_create(db: Session, tenant_id: int, _args: DraftCreateArguments, identity: VerifiedCustomerIdentity) -> dict[str, Any]:
    now = _now()
    public_id = _hash(f"{tenant_id}:{_owner(identity)}:{_args.idempotency_key}")[:32]
    existing = db.query(WazzaOrderDraft).filter(WazzaOrderDraft.public_id == public_id).first()
    if existing is not None:
        return {"draft": _summary(existing)}
    draft = WazzaOrderDraft(
        public_id=public_id, tenant_id=tenant_id, owner_hash=_owner(identity),
        conversation_hash=_hash(identity.conversation_id) if identity.conversation_id else None,
        status="active", items_json=[], mutation_keys_json={}, version=1, created_at=now, updated_at=now, expires_at=now + DRAFT_TTL,
    )
    db.add(draft)
    db.flush()
    return {"draft": _summary(draft)}


def order_draft_add_item(db: Session, tenant_id: int, args: DraftAddItemArguments, identity: VerifiedCustomerIdentity) -> dict[str, Any]:
    draft = _get_draft(db, tenant_id, identity, args.draft_id, for_write=True)
    if _is_replay(draft, args):
        return {"draft": _summary(draft)}
    items = list(draft.items_json or [])
    items.append(_price_line(db, tenant_id, args.item_id, args.quantity, args.modifier_option_ids, args.notes))
    draft.items_json = items
    _record_mutation(draft, args)
    _touch(draft)
    return {"draft": _summary(draft)}


def order_draft_update_item(db: Session, tenant_id: int, args: DraftUpdateItemArguments, identity: VerifiedCustomerIdentity) -> dict[str, Any]:
    draft = _get_draft(db, tenant_id, identity, args.draft_id, for_write=True)
    if _is_replay(draft, args):
        return {"draft": _summary(draft)}
    items = list(draft.items_json or [])
    index = next((i for i, item in enumerate(items) if item.get("line_id") == args.line_id), None)
    if index is None:
        raise McpToolError("draft_line_not_found", "Item do rascunho não encontrado.")
    current = items[index]
    option_ids = args.modifier_option_ids if args.modifier_option_ids is not None else [int(entry["option_id"]) for entry in current.get("modifiers", [])]
    notes = args.notes if args.notes is not None else current.get("notes")
    quantity = args.quantity if args.quantity is not None else int(current["quantity"])
    items[index] = _price_line(db, tenant_id, int(current["item_id"]), quantity, option_ids, notes, line_id=args.line_id)
    draft.items_json = items
    _record_mutation(draft, args)
    _touch(draft)
    return {"draft": _summary(draft)}


def order_draft_remove_item(db: Session, tenant_id: int, args: DraftRemoveItemArguments, identity: VerifiedCustomerIdentity) -> dict[str, Any]:
    draft = _get_draft(db, tenant_id, identity, args.draft_id, for_write=True)
    if _is_replay(draft, args):
        return {"draft": _summary(draft)}
    items = [item for item in list(draft.items_json or []) if item.get("line_id") != args.line_id]
    if len(items) == len(list(draft.items_json or [])):
        raise McpToolError("draft_line_not_found", "Item do rascunho não encontrado.")
    draft.items_json = items
    _record_mutation(draft, args)
    _touch(draft)
    return {"draft": _summary(draft)}


def order_draft_set_delivery(db: Session, tenant_id: int, args: DraftDeliveryArguments, identity: VerifiedCustomerIdentity) -> dict[str, Any]:
    draft = _get_draft(db, tenant_id, identity, args.draft_id, for_write=True)
    if _is_replay(draft, args):
        return {"draft": _summary(draft)}
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        raise McpToolError("restaurant_not_found", "Restaurante não encontrado.")
    draft.fulfillment_json = {
        "type": args.fulfillment_type,
        "address": args.address.model_dump() if args.address else None,
        "delivery_fee_cents": _money_cents(tenant.delivery_fee) if args.fulfillment_type == "delivery" else 0,
    }
    _record_mutation(draft, args)
    _touch(draft)
    return {"draft": _summary(draft)}


def order_draft_set_payment(db: Session, tenant_id: int, args: DraftPaymentArguments, identity: VerifiedCustomerIdentity) -> dict[str, Any]:
    draft = _get_draft(db, tenant_id, identity, args.draft_id, for_write=True)
    if _is_replay(draft, args):
        return {"draft": _summary(draft)}
    draft.payment_json = {"method": args.payment_method, "change_for_cents": args.change_for_cents}
    _record_mutation(draft, args)
    _touch(draft)
    return {"draft": _summary(draft)}


def quote_draft(db: Session, tenant_id: int, draft: WazzaOrderDraft) -> dict[str, Any]:
    repriced = []
    for current in list(draft.items_json or []):
        repriced.append(_price_line(db, tenant_id, int(current["item_id"]), int(current["quantity"]), [int(entry["option_id"]) for entry in current.get("modifiers", [])], current.get("notes"), line_id=current["line_id"]))
    summary = _summary(draft, items_override=repriced)
    summary["expires_at"] = require_fresh_draft(draft).isoformat()
    if summary["fulfillment"] and summary["fulfillment"]["type"] == "delivery":
        fee = db.query(Tenant.delivery_fee).filter(Tenant.id == tenant_id).scalar()
        summary["delivery_fee_cents"] = _money_cents(fee)
        summary["fulfillment"] = {**summary["fulfillment"], "delivery_fee_cents": summary["delivery_fee_cents"]}
        summary["total_cents"] = summary["subtotal_cents"] + summary["delivery_fee_cents"]
    summary["discount_cents"] = 0
    summary["ready_to_confirm"] = bool(repriced and draft.fulfillment_json and draft.payment_json)
    summary["creates_order"] = False
    return summary


def order_draft_quote(db: Session, tenant_id: int, args: DraftRefArguments, identity: VerifiedCustomerIdentity) -> dict[str, Any]:
    from app.services.wazza_mcp_confirmation import confirmation_available, issue_quote_token

    draft = _get_draft(db, tenant_id, identity, args.draft_id)
    summary = quote_draft(db, tenant_id, draft)
    if summary["ready_to_confirm"] and confirmation_available():
        summary.update(issue_quote_token(draft, summary, identity))
    return {"quote": summary}


def _definition(title: str, description: str, model: type[BaseModel], handler, *, risk: str = "write", idempotent: bool = False) -> dict[str, Any]:
    return {"title": title, "description": description, "scope": "order:draft", "arguments_model": model, "handler": handler, "requires_customer": True, "risk": risk, "idempotent": idempotent}


DRAFT_TOOL_DEFINITIONS = {
    "order_draft_create": _definition("Criar rascunho", "Cria um carrinho isolado; não envia pedido ao restaurante.", DraftCreateArguments, order_draft_create),
    "order_draft_add_item": _definition("Adicionar item ao rascunho", "Adiciona item usando catálogo e preços atuais do servidor.", DraftAddItemArguments, order_draft_add_item),
    "order_draft_update_item": _definition("Alterar item do rascunho", "Altera quantidade, adicionais ou observação de uma linha própria.", DraftUpdateItemArguments, order_draft_update_item),
    "order_draft_remove_item": _definition("Remover item do rascunho", "Remove uma linha do rascunho próprio.", DraftRemoveItemArguments, order_draft_remove_item),
    "order_draft_set_delivery": _definition("Definir entrega do rascunho", "Define entrega ou retirada sem criar pedido.", DraftDeliveryArguments, order_draft_set_delivery),
    "order_draft_set_payment": _definition("Definir pagamento do rascunho", "Registra a preferência de pagamento sem cobrar ou marcar como pago.", DraftPaymentArguments, order_draft_set_payment),
    "order_draft_quote": _definition("Calcular orçamento do rascunho", "Revalida disponibilidade e preços no servidor; não cria pedido.", DraftRefArguments, order_draft_quote, risk="read", idempotent=True),
}
