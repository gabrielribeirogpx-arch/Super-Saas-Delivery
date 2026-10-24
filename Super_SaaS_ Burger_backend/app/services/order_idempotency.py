"""A receipt is committed together with its order; no committed reservations."""
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
import hashlib
import hmac
import json
import re

from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.models.order_durability import OrderSubmission

RETENTION = timedelta(days=7)


@dataclass(frozen=True)
class Attempt:
    tenant_id: int
    key_hash: str
    request_hash: str


def make_attempt(tenant_id, key, payload, *, customer_id=None, modifiers=None):
    if key is None:
        return None  # Existing integrations remain compatible; new storefront sends a key.
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", key):
        raise HTTPException(400, "Chave de tentativa de pedido inválida")
    canonical = json.dumps({"tenant_id": tenant_id, "customer_id": customer_id,
        "payload": payload.model_dump(mode="json"),
        "modifiers": {str(i): [entry.model_dump(mode="json") for entry in entries]
                      for i, entries in (modifiers or {}).items()}},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return Attempt(tenant_id, hashlib.sha256(key.encode()).hexdigest(), hashlib.sha256(canonical.encode()).hexdigest())


def checked_response(row, attempt):
    if not hmac.compare_digest(row.request_hash, attempt.request_hash):
        raise HTTPException(409, "Esta tentativa já foi usada com outros dados. Confira seus pedidos antes de tentar novamente.")
    if row.order_id is None or row.response_json is None:
        raise HTTPException(409, "Pedido em processamento. Aguarde e repita a mesma tentativa.")
    return row.response_json


def replay(db, attempt):
    if attempt is None:
        return None
    row = db.get(OrderSubmission, (attempt.tenant_id, attempt.key_hash))
    return checked_response(row, attempt) if row is not None else None


def reserve(db, attempt):
    """Unique insert waits for a competing transaction, without an ASGI lock.

    Returns (new receipt, None), or (None, the already committed response).
    The caller must roll back the reservation on *any* order failure.
    """
    if attempt is None:
        return None, None
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    now = datetime.now(timezone.utc)
    inserted = db.execute(insert(OrderSubmission).values(tenant_id=attempt.tenant_id,
        key_hash=attempt.key_hash, request_hash=attempt.request_hash,
        created_at=now, expires_at=now + RETENTION).on_conflict_do_nothing(
            index_elements=["tenant_id", "key_hash"]).returning(OrderSubmission.key_hash)).scalar_one_or_none()
    row = db.get(OrderSubmission, (attempt.tenant_id, attempt.key_hash), populate_existing=True)
    if inserted is not None:
        return row, None
    if row is None:
        raise RuntimeError("order_receipt_unavailable")
    return None, checked_response(row, attempt)


def complete(receipt, order, response):
    if receipt is not None:
        receipt.order_id = order.id
        receipt.response_json = response.model_dump(mode="json")
