"""Durable secondary verification; independent of future signature validation."""
from datetime import datetime, timedelta, timezone
import json
import secrets

from sqlalchemy import or_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models.billing_event import BillingEvent, BillingEventStatus, BillingVerificationStatus as V
from app.models.billing_provider_budget import BillingProviderBudget
from app.models.billing_checkout_intent import BillingCheckoutIntent, BillingIntentStatus
from app.models.subscription import Subscription, SubscriptionStatus as S
from app.services.billing_catalog import BillingCatalogService
from app.services.billing_common import BillingError, utc
from app.services.kiwify_api import KiwifySalesAPI, VerificationOutcome, VerificationUnavailable, VerificationThrottled, VerifiedSubscription
from app.services.kiwify_projection import validate_projection
from app.services.subscriptions import SubscriptionActor, SubscriptionService
from app.services.admin_audit import log_admin_action


class KiwifyVerificationService:
    def __init__(self, session_factory, settings, *, source=None, clock=None):
        self.sessions = session_factory
        self.settings = settings
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.source = source or KiwifySalesAPI(settings, reserve=self.reserve_requests)

    def reserve_requests(self):
        now = utc(self.clock())
        with self.sessions() as db, db.begin():
            insert = {"sqlite": sqlite_insert, "postgresql": pg_insert}[db.get_bind().dialect.name]
            db.execute(insert(BillingProviderBudget).values(provider="kiwify", next_request_at=now)
                       .on_conflict_do_nothing(index_elements=["provider"]))
            reserved = db.execute(update(BillingProviderBudget).where(
                BillingProviderBudget.provider == "kiwify", BillingProviderBudget.next_request_at <= now)
                .values(next_request_at=now + timedelta(seconds=3)).returning(BillingProviderBudget.provider)).scalar_one_or_none()
            if reserved is None:
                raise VerificationThrottled("kiwify_request_budget_busy")

    def verify_event(self, event_id):
        if not self.settings.enabled:
            return None
        now, lease = utc(self.clock()), secrets.token_hex(16)
        with self.sessions() as db, db.begin():
            claimed = db.execute(update(BillingEvent).where(
                BillingEvent.id == event_id, BillingEvent.provider == "kiwify", BillingEvent.schema_version == 2,
                BillingEvent.environment == self.settings.environment,
                BillingEvent.provider_account_id == self.settings.account_id,
                BillingEvent.processing_status == BillingEventStatus.PENDING,
                BillingEvent.verification_status.in_([V.PENDING, V.RETRYING]),
                or_(BillingEvent.verification_next_at.is_(None), BillingEvent.verification_next_at <= now),
                or_(BillingEvent.verification_lease_until.is_(None), BillingEvent.verification_lease_until <= now))
                .values(verification_lease_token=lease, verification_lease_until=now + timedelta(minutes=2),
                        verification_attempts=BillingEvent.verification_attempts + 1)
                .returning(BillingEvent.id)).scalar_one_or_none()
            if claimed is None:
                return None
            event = db.get(BillingEvent, event_id)
            projection = json.loads(event.raw_payload).get("projection")
            attempts = event.verification_attempts
        # No DB locks/transaction are held while querying the provider.
        try:
            validate_projection(projection)
            outcome = self.source.verify(projection)
        except VerificationThrottled:
            outcome = VerificationOutcome(V.RETRYING, "verification_rate_limited")
        except VerificationUnavailable:
            outcome = VerificationOutcome(V.RETRYING if attempts < 8 else V.MANUAL_REVIEW,
                                          "verification_unavailable" if attempts < 8 else "verification_retries_exhausted")
        except Exception:
            # Never log exceptions from integrations, which may contain PII/headers.
            outcome = VerificationOutcome(V.MANUAL_REVIEW, "verification_response_invalid")
        try:
            return self._finish(event_id, lease, projection, outcome)
        except BillingError:
            return self._finish(event_id, lease, projection, VerificationOutcome(V.MANUAL_REVIEW, "trusted_correlation_or_transition_unavailable"))

    def _finish(self, event_id, lease, projection, outcome):
        now = utc(self.clock())
        with self.sessions() as db, db.begin():
            # CAS acquires a write lock even on SQLite; stale workers cannot apply.
            fenced = db.execute(update(BillingEvent).where(BillingEvent.id == event_id,
                BillingEvent.verification_lease_token == lease, BillingEvent.verification_lease_until > now)
                .values(verification_lease_until=now + timedelta(minutes=2)).returning(BillingEvent.id)).scalar_one_or_none()
            if fenced is None:
                return None
            event = db.get(BillingEvent, event_id)
            if outcome.status == V.VERIFIED:
                self._apply(db, event, projection, outcome.subscription, now)
                event.verified_at = now
            elif outcome.status not in {V.REJECTED, V.MANUAL_REVIEW, V.RETRYING}:
                raise BillingError("invalid_verification_outcome")
            event.verification_status = outcome.status
            event.verification_error_code = outcome.code
            event.verification_lease_token = None
            event.verification_lease_until = None
            if outcome.code == "verification_rate_limited":
                event.verification_attempts = max(0, event.verification_attempts - 1)
                event.verification_next_at = now + timedelta(seconds=3)
            else:
                event.verification_next_at = (now + timedelta(seconds=min(3600, 30 * 2 ** min(event.verification_attempts - 1, 7)))) if outcome.status == V.RETRYING else None
            db.flush()
            return outcome.status

    def _apply(self, db, event, projection, proof, now):
        if not isinstance(proof, VerifiedSubscription) or (proof.account_id, proof.environment) != (event.provider_account_id, event.environment):
            raise BillingError("trusted_evidence_missing")
        if proof.observed_at.tzinfo is None or not now - timedelta(minutes=5) <= utc(proof.observed_at) <= now:
            raise BillingError("trusted_evidence_not_fresh")
        if any(projection.get(field) != value for field, value in (
            ("order_id", proof.sale_id), ("subscription_id", proof.subscription_id),
            ("product_id", proof.product_id), ("plan_id", proof.plan_id))):
            raise BillingError("trusted_evidence_mismatch")
        mapping = BillingCatalogService(db).resolve_mapping(provider="kiwify", environment=event.environment,
            provider_account_id=event.provider_account_id, external_product_id=proof.product_id, external_offer_id=proof.plan_id)
        intents = db.query(BillingCheckoutIntent).filter_by(provider="kiwify", environment=event.environment,
            provider_account_id=event.provider_account_id, status=BillingIntentStatus.COMPLETED,
            external_subscription_id=proof.subscription_id, plan_id=mapping.plan_id).limit(2).all()
        if len(intents) != 1:
            raise BillingError("trusted_correlation_missing_or_ambiguous")
        intent = intents[0]
        if event.tenant_id is not None and event.tenant_id != intent.tenant_id:
            raise BillingError("existing_tenant_correlation_mismatch")
        if event.checkout_intent_id is not None and event.checkout_intent_id != intent.id:
            raise BillingError("existing_intent_correlation_mismatch")
        sub = db.query(Subscription).filter_by(tenant_id=intent.tenant_id).with_for_update().one_or_none()
        if event.subscription_id is not None and (sub is None or event.subscription_id != sub.id):
            raise BillingError("existing_subscription_correlation_mismatch")
        actor = SubscriptionActor(actor_type="provider", origin="kiwify_secondary_verification", correlation_id=str(event.id))
        service = SubscriptionService(db, clock=lambda: now)
        if sub is not None and (sub.provider != "kiwify" or sub.provider_subscription_id != proof.subscription_id or sub.plan_id != mapping.plan_id):
            raise BillingError("trusted_subscription_binding_mismatch")
        if proof.status == S.ACTIVE:
            start, end = utc(proof.period_start), utc(proof.period_end)
            if proof.period_start.tzinfo is None or proof.period_end.tzinfo is None or start > now or end <= now or end <= start:
                raise BillingError("trusted_period_invalid")
            if sub is None:
                sub = service.create_subscription(intent.tenant_id, mapping.plan_id, actor=actor,
                    provider="kiwify", provider_subscription_id=proof.subscription_id)
            if sub.status in {S.INACTIVE, S.TRIALING, S.PAST_DUE}:
                service.activate_subscription(sub.tenant_id, sub.id, current_period_start=start, current_period_end=end, actor=actor, expected_version=sub.version)
            elif sub.status == S.ACTIVE:
                if sub.current_period_end is None:
                    raise BillingError("trusted_current_period_missing")
                if end > utc(sub.current_period_end):
                    service.renew_subscription(sub.tenant_id, sub.id, current_period_start=start,
                        current_period_end=end, actor=actor, expected_version=sub.version)
            else:
                raise BillingError("terminal_subscription_requires_review")
        elif proof.status == S.PAST_DUE and sub is not None:
            if sub.status != S.PAST_DUE:
                service.mark_past_due(sub.tenant_id, sub.id, actor=actor, expected_version=sub.version)
        elif proof.status == S.CANCELED and sub is not None:
            # Cancellation timing is a commercial policy not confirmed by docs.
            raise BillingError("cancellation_policy_requires_review")
        else:
            raise BillingError("unsupported_trusted_subscription_state")
        event.tenant_id, event.subscription_id, event.checkout_intent_id = sub.tenant_id, sub.id, intent.id
        event.processing_status, event.processed_at = BillingEventStatus.PROCESSED, now
        log_admin_action(db, tenant_id=sub.tenant_id, user_id=None, actor_type="provider", action="billing.event_verified",
            entity_type="subscription", entity_id=sub.id, meta={"billing_event_id": event.id, "origin": "kiwify_secondary_verification"})

    def run_pending(self, limit=50):
        if not self.settings.enabled:
            return []
        now = utc(self.clock())
        with self.sessions() as db:
            ids = [row[0] for row in db.query(BillingEvent.id).filter(
                BillingEvent.provider == "kiwify", BillingEvent.schema_version == 2,
                BillingEvent.processing_status == BillingEventStatus.PENDING,
                BillingEvent.provider_account_id == self.settings.account_id, BillingEvent.environment == self.settings.environment,
                BillingEvent.verification_status.in_([V.PENDING, V.RETRYING]),
                or_(BillingEvent.verification_next_at.is_(None), BillingEvent.verification_next_at <= now),
                or_(BillingEvent.verification_lease_until.is_(None), BillingEvent.verification_lease_until <= now))
                .order_by(BillingEvent.id).limit(limit)]
        return [self.verify_event(event_id) for event_id in ids]
