"""Lease-based operational worker. Provider delivery is at-least-once.

Receipts deduplicate known effects; a provider accepting a message and losing its
response can still result in a repeated notification. Never run payment calls.
"""
import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import and_, or_, exists, select, update, delete, func, tuple_
from sqlalchemy.orm import aliased
from starlette.concurrency import run_in_threadpool

from app.models.order_durability import OrderOutbox, OrderEffectReceipt, OrderSubmission
from app.models.order import Order
from app.services.order_events import build_order_payload, _build_tracking_url
from app.services.customer_stats import update_customer_stats_for_order
from app.services.whatsapp_outbound import send_whatsapp_message
from app.realtime.publisher import publish_delivery_assignment_event

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 8
LEASE = timedelta(minutes=5)
TEMPLATES = {"EM_PREPARO": "order_in_preparation", "PRONTO": "order_ready",
             "SAIU_PARA_ENTREGA": "order_out_for_delivery", "ENTREGUE": "order_delivered"}


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


@dataclass(frozen=True)
class Claim:
    id: int
    tenant_id: int
    order_id: int
    effect: str
    payload: dict
    token: str


def claim_one(sessions, now):
    older = aliased(OrderOutbox)
    with sessions() as db, db.begin():
        # A crash on the final allowed attempt must not leave processing forever.
        db.execute(update(OrderOutbox).where(OrderOutbox.status == "processing",
            OrderOutbox.lease_until <= now, OrderOutbox.attempts >= MAX_ATTEMPTS).values(
                status="review", lease_token=None, lease_until=None, error_code="lease_exhausted"))
        predecessor = exists(select(older.id).where(older.tenant_id == OrderOutbox.tenant_id,
            older.order_id == OrderOutbox.order_id, older.stream == OrderOutbox.stream,
            older.id < OrderOutbox.id, older.status != "done"))
        row = db.query(OrderOutbox).filter(OrderOutbox.attempts < MAX_ATTEMPTS,
            or_(and_(OrderOutbox.status == "pending", OrderOutbox.next_attempt_at <= now),
                and_(OrderOutbox.status == "processing", OrderOutbox.lease_until <= now)),
            ~predecessor).order_by(OrderOutbox.next_attempt_at, OrderOutbox.id).with_for_update(skip_locked=True).first()
        if row is None:
            return None
        token = uuid4().hex
        # CAS also makes local SQLite development safe without SKIP LOCKED.
        condition = or_(and_(OrderOutbox.status == "pending", OrderOutbox.next_attempt_at <= now),
                        and_(OrderOutbox.status == "processing", OrderOutbox.lease_until <= now))
        changed = db.execute(update(OrderOutbox).where(OrderOutbox.id == row.id, condition,
            OrderOutbox.attempts == row.attempts).values(status="processing", lease_token=token,
            lease_until=now + LEASE, attempts=row.attempts + 1).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            return None
        return Claim(row.id, row.tenant_id, row.order_id, row.effect, dict(row.payload), token)


def _owned(db, claim, now):
    return db.query(OrderOutbox).filter_by(id=claim.id, tenant_id=claim.tenant_id,
        status="processing", lease_token=claim.token).filter(OrderOutbox.lease_until > now).one_or_none()


def effect_key(claim):
    if claim.effect == "customer.delivered":
        return "customer.delivered"
    if claim.effect.startswith("whatsapp."):
        template = "order_confirmed" if claim.effect == "whatsapp.created" else TEMPLATES.get(claim.payload["status"])
        return "whatsapp:" + template if template else None
    return None


def _receipt(db, claim, key):
    return db.get(OrderEffectReceipt, (claim.tenant_id, claim.order_id, key)) if key else None


def _done(db, claim, now):
    return db.execute(update(OrderOutbox).where(OrderOutbox.id == claim.id,
        OrderOutbox.tenant_id == claim.tenant_id, OrderOutbox.status == "processing",
        OrderOutbox.lease_token == claim.token, OrderOutbox.lease_until > now).values(
        status="done", completed_at=now, lease_token=None, lease_until=None,
        error_code=None).execution_options(synchronize_session=False)).rowcount == 1


def _payload(db, claim):
    order = db.query(Order).filter_by(id=claim.order_id, tenant_id=claim.tenant_id).one()
    payload = build_order_payload(order)
    payload.update(claim.payload)
    # Resolve current token validity; never persist tokens in the queue payload.
    if payload["status"] == "SAIU_PARA_ENTREGA":
        payload["tracking_url"] = _build_tracking_url(order) or ""
    return order, payload


def dispatch(sessions, claim, clock):
    key = effect_key(claim)
    if claim.effect == "customer.delivered":
        # Effect, receipt and acknowledgement commit atomically. Serialize stats
        # for a tenant so first-time customer rows cannot race into duplicates.
        with sessions() as db, db.begin():
            if _owned(db, claim, clock()) is None:
                return False
            if db.get_bind().dialect.name == "postgresql":
                # Avoid tenant row locks: operational transactions insert rows
                # with tenant/order FKs, so mixing those locks can deadlock.
                db.execute(select(func.pg_advisory_xact_lock(0x464F4D, claim.tenant_id)))
            if _receipt(db, claim, key) is None:
                order, _ = _payload(db, claim)
                update_customer_stats_for_order(db, order)
                db.add(OrderEffectReceipt(tenant_id=claim.tenant_id, order_id=claim.order_id,
                                         effect_key=key, completed_at=clock()))
            if not _done(db, claim, clock()):
                db.rollback()
                return False
            return True

    with sessions() as db:
        if _owned(db, claim, clock()) is None:
            return False
        already_done = _receipt(db, claim, key) is not None
        if not already_done:
            _, payload = _payload(db, claim)
            if claim.effect.startswith("whatsapp."):
                template = "order_confirmed" if claim.effect == "whatsapp.created" else TEMPLATES.get(payload["status"])
                if template:
                    result = send_whatsapp_message(db, tenant_id=claim.tenant_id,
                        phone=payload["customer_phone"], template=template, order_id=claim.order_id,
                        variables={"customer_name": payload["customer_name"] or "Cliente",
                            "order_number": payload["order_number"], "total_cents": payload["total_cents"],
                            "estimated_time": payload["estimated_time"], "tracking_url": payload.get("tracking_url", "")})
                    if result is not None and result.status == "failed" and result.error != "opt_out":
                        raise RuntimeError("whatsapp_delivery_failed")
            elif claim.effect == "delivery.status":
                driver = payload.get("assigned_delivery_user_id")
                if driver is not None:
                    publish_delivery_assignment_event(claim.tenant_id, claim.order_id, int(driver), payload, strict=True)
            else:
                raise RuntimeError("unknown_order_effect")
        # Provider helpers may commit their own delivery log. Ack is conditional
        # on the lease; an obsolete worker cannot acknowledge a newer owner.
        if _done(db, claim, clock()):
            if key and not already_done:
                db.add(OrderEffectReceipt(tenant_id=claim.tenant_id, order_id=claim.order_id,
                    effect_key=key, completed_at=clock()))
            db.commit()
            return True
        db.rollback()
        return False


def fail(sessions, claim, now):
    with sessions() as db, db.begin():
        row = _owned(db, claim, now)
        if row is None:
            return
        attempts = row.attempts
        db.execute(update(OrderOutbox).where(OrderOutbox.id == claim.id,
            OrderOutbox.lease_token == claim.token, OrderOutbox.status == "processing").values(
                status="review" if attempts >= MAX_ATTEMPTS else "pending",
                next_attempt_at=now + timedelta(seconds=min(3600, 5 * 2 ** min(attempts, 10))),
                lease_token=None, lease_until=None, error_code="effect_failed"))


def run_cycle(sessions, *, batch_size=20, clock=None, handler=None, should_stop=None):
    clock = clock or (lambda: datetime.now(timezone.utc))
    handler = handler or dispatch
    counts = {"done": 0, "retry": 0, "lost_lease": 0}
    for _ in range(batch_size):
        if should_stop is not None and should_stop():
            break
        claim = claim_one(sessions, clock())
        if claim is None:
            break
        try:
            if handler(sessions, claim, clock):
                counts["done"] += 1
            else:
                counts["lost_lease"] += 1
        except Exception:
            # Exceptions from providers may contain tokens, PII or full URLs.
            fail(sessions, claim, clock())
            counts["retry"] += 1
            logger.warning("order_effect_retry job_id=%s effect=%s", claim.id, claim.effect)
    return counts


def cleanup(sessions, *, now=None, limit=2000):
    now = now or datetime.now(timezone.utc)
    with sessions() as db, db.begin():
        keys = db.query(OrderSubmission.tenant_id, OrderSubmission.key_hash).filter(
            OrderSubmission.expires_at < now, OrderSubmission.order_id.is_not(None)).limit(limit).all()
        if keys:
            db.execute(delete(OrderSubmission).where(
                tuple_(OrderSubmission.tenant_id, OrderSubmission.key_hash).in_(keys),
                OrderSubmission.expires_at < now, OrderSubmission.order_id.is_not(None)))
        ids = [i for i, in db.query(OrderOutbox.id).filter(OrderOutbox.status == "done",
            OrderOutbox.completed_at < now - timedelta(days=7)).order_by(OrderOutbox.id).limit(limit)]
        if ids:
            db.execute(delete(OrderOutbox).where(OrderOutbox.id.in_(ids), OrderOutbox.status == "done"))
        return {"receipts_deleted": len(keys), "jobs_deleted": len(ids)}


def stats(sessions):
    with sessions() as db:
        counts = dict(db.query(OrderOutbox.status, func.count()).group_by(OrderOutbox.status).all())
        oldest = db.query(func.min(OrderOutbox.created_at)).filter(OrderOutbox.status.in_(["pending", "processing", "review"])).scalar()
        return {"counts": counts, "oldest_unfinished_at": utc(oldest).isoformat() if oldest else None}


def retry_review(sessions, job_id):
    with sessions() as db, db.begin():
        result = db.execute(update(OrderOutbox).where(OrderOutbox.id == job_id,
            OrderOutbox.status == "review").values(status="pending", attempts=0,
                next_attempt_at=datetime.now(timezone.utc), lease_token=None,
                lease_until=None, error_code=None))
        return result.rowcount == 1


def embedded_enabled():
    from app.core.config import ENV_NORMALIZED
    default = "true" if ENV_NORMALIZED in {"production", "prod", "staging", "stage", "homolog"} else "false"
    value = os.getenv("ORDER_OUTBOX_EMBEDDED", default).strip().lower()
    if value not in {"1", "true", "yes", "0", "false", "no"}:
        raise RuntimeError("invalid_order_outbox_embedded_setting")
    return value in {"1", "true", "yes"}


async def run_loop(sessions, stop_event):
    last_cleanup = 0
    while not stop_event.is_set():
        try:
            result = await run_in_threadpool(run_cycle, sessions, batch_size=10, should_stop=stop_event.is_set)
            if asyncio.get_running_loop().time() - last_cleanup > 60:
                await run_in_threadpool(cleanup, sessions)
                last_cleanup = asyncio.get_running_loop().time()
            delay = .1 if result["done"] else 1.0
        except Exception:
            logger.warning("order_outbox_cycle_failed")
            delay = 5.0
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass
