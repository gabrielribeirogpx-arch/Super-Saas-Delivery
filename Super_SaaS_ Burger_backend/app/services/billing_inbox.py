"""Durable internal inbox. Adapters/authenticated ingress are deliberately absent."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping

from sqlalchemy import or_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.billing_checkout_intent import BillingCheckoutIntent, BillingIntentStatus
from app.models.billing_event import BillingEvent, BillingEventStatus
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.services.billing_common import BillingConflict, BillingError, billing_transaction, identifier, scope, utc


@dataclass(frozen=True)
class BillingReceipt:
    event: BillingEvent
    created: bool


class BillingInboxService:
    def __init__(self, db: Session):
        self.db = db

    def receive_event(self, *, provider: str, environment: str, provider_account_id: str,
                      provider_event_id: str, event_type: str, payload: Mapping[str, Any],
                      schema_version: int = 1, occurred_at: datetime | None = None) -> BillingReceipt:
        scope(provider, environment)
        identifier(provider_account_id)
        identifier(provider_event_id)
        identifier(event_type, 100)
        if type(schema_version) is not int or schema_version < 1:
            raise BillingError("invalid_schema_version")
        if not isinstance(payload, Mapping):
            raise BillingError("invalid_payload")
        try:
            canonical = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise BillingError("invalid_payload") from exc
        if len(canonical) > 1024 * 1024:
            raise BillingError("payload_too_large")
        digest = hashlib.sha256(canonical).hexdigest()
        # The original payload is intentionally discarded; this is a protected receipt.
        protected = json.dumps({"redacted": True, "payload_hash": digest, "schema_version": schema_version})
        key = dict(provider=provider, environment=environment, provider_account_id=provider_account_id, provider_event_id=provider_event_id)
        occurred_at = utc(occurred_at) if occurred_at is not None else None
        dialect = self.db.get_bind().dialect.name
        insert = {"sqlite": sqlite_insert, "postgresql": pg_insert}.get(dialect)
        if insert is None:
            raise BillingError("unsupported_billing_database")
        with billing_transaction(self.db):
            stmt = insert(BillingEvent).values(**key, event_type=event_type, payload_hash=digest, raw_payload=protected,
                schema_version=schema_version, occurred_at=occurred_at, processing_status=BillingEventStatus.PENDING, attempt_count=0)
            # Unique constraint and ON CONFLICT serialize competing deliveries in the DB.
            event_id = self.db.execute(stmt.on_conflict_do_nothing(index_elements=[
                "provider", "provider_account_id", "environment", "provider_event_id"]).returning(BillingEvent.id)).scalar_one_or_none()
            event = self.db.query(BillingEvent).filter_by(**key).one()
            stored_time = utc(event.occurred_at) if event.occurred_at is not None else None
            if event.payload_hash != digest or event.event_type != event_type or event.schema_version != schema_version or stored_time != occurred_at:
                raise BillingConflict("event_identity_payload_mismatch")
            return BillingReceipt(event=event, created=event_id is not None)

    def link_event(self, event_id: int, tenant_id: int, *, subscription_id: int | None = None,
                   checkout_intent_id: int | None = None, now: datetime | None = None) -> BillingEvent:
        """Link only from trusted internal IDs; never infer tenancy from payload/email."""
        now = utc(now or datetime.now(timezone.utc))
        with billing_transaction(self.db):
            event = (self.db.query(BillingEvent).filter_by(id=event_id)
                     .populate_existing().with_for_update().one_or_none())
            if event is None:
                raise BillingError("event_not_found")
            if self.db.get(Tenant, tenant_id) is None:
                raise BillingError("tenant_not_found")
            if event.processing_status != BillingEventStatus.PENDING:
                raise BillingError("event_not_pending")
            if event.tenant_id is not None and event.tenant_id != tenant_id:
                raise BillingError("event_tenant_mismatch")
            subscription_id = subscription_id if subscription_id is not None else event.subscription_id
            checkout_intent_id = checkout_intent_id if checkout_intent_id is not None else event.checkout_intent_id
            if subscription_id is not None:
                sub = self.db.query(Subscription).filter_by(id=subscription_id, tenant_id=tenant_id).one_or_none()
                if sub is None:
                    raise BillingError("subscription_not_found")
                if sub.provider is not None and sub.provider != event.provider:
                    raise BillingError("event_provider_mismatch")
            if checkout_intent_id is not None:
                intent = self.db.query(BillingCheckoutIntent).filter_by(id=checkout_intent_id, tenant_id=tenant_id).one_or_none()
                if intent is None:
                    raise BillingError("intent_not_found")
                if (intent.provider, intent.environment, intent.provider_account_id) != (event.provider, event.environment, event.provider_account_id):
                    raise BillingError("event_intent_scope_mismatch")
                if intent.status in {BillingIntentStatus.EXPIRED, BillingIntentStatus.CANCELED} or (
                    intent.status == BillingIntentStatus.PENDING and utc(intent.expires_at) <= now
                ):
                    raise BillingError("intent_expired_or_canceled")
                if intent.status == BillingIntentStatus.COMPLETED and subscription_id is not None and (
                    intent.external_subscription_id is not None and sub.provider_subscription_id != intent.external_subscription_id
                ):
                    raise BillingError("event_subscription_binding_mismatch")
            # Once attached, links are immutable. SQL predicates also protect concurrent writers.
            conditions = [BillingEvent.id == event_id, BillingEvent.processing_status == BillingEventStatus.PENDING,
                          or_(BillingEvent.tenant_id.is_(None), BillingEvent.tenant_id == tenant_id)]
            values = {"tenant_id": tenant_id}
            for name, value in (("subscription_id", subscription_id), ("checkout_intent_id", checkout_intent_id)):
                if value is not None:
                    column = getattr(BillingEvent, name)
                    conditions.append(or_(column.is_(None), column == value))
                    values[name] = value
                else:
                    conditions.append(getattr(BillingEvent, name).is_(None))
            result = self.db.execute(update(BillingEvent).where(*conditions).values(**values).execution_options(synchronize_session=False))
            if result.rowcount != 1:
                raise BillingConflict("event_link_conflict")
            self.db.refresh(event)
            return event
