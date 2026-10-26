"""Tenant-scoped review. Human approval never upgrades webhook evidence to truth."""
from datetime import datetime, timedelta, timezone
import json

from sqlalchemy import and_, or_, update
from sqlalchemy.exc import OperationalError

from app.models.admin_user import AdminUser
from app.models.billing_checkout_intent import BillingCheckoutIntent, BillingIntentStatus
from app.models.billing_event import BillingEvent, BillingEventStatus as P, BillingVerificationStatus as V
from app.models.billing_manual_review import BillingManualReview
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.services.admin_audit import log_admin_action
from app.services.billing_catalog import BillingCatalogService
from app.services.billing_common import BillingConflict, BillingError, billing_transaction, utc
from app.services.kiwify_api import VerifiedSubscription
from app.services.kiwify_projection import validate_projection
from app.services.kiwify_verification import KiwifyVerificationService
from app.services.subscriptions import SubscriptionActor, SubscriptionService
from app.models.subscription import Subscription, SubscriptionStatus as S

REJECTION_REASONS = {"incorrect_binding", "incorrect_plan", "duplicate_sale", "invalid_sale", "insufficient_evidence"}
SAFE_REASONS = {"sale_confirmed_subscription_unconfirmed", "api_sale_not_paid", "api_credentials_unavailable",
    "api_credentials_or_scope_invalid", "api_sale_response_invalid", "api_sale_response_incomplete",
    "api_token_response_invalid", "verification_response_invalid", "verification_retries_exhausted",
    "subscription_endpoint_unconfirmed", "trusted_correlation_or_transition_unavailable", "manual_review_period_missing"}


class ReviewNotFound(BillingError):
    pass


class BillingManualReviewService:
    def __init__(self, db, *, clock=None):
        self.db = db
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _authorize(self, user):
        actual = self.db.get(AdminUser, user.id)
        if actual is None or not actual.active or actual.tenant_id != user.tenant_id or actual.role.strip().lower() not in {"admin", "owner"}:
            raise BillingError("review_forbidden")

    def _context(self, event):
        review = self.db.get(BillingManualReview, event.id)
        projection = None
        try:
            projection = json.loads(event.raw_payload)["projection"]
            validate_projection(projection)
        except (ValueError, KeyError, TypeError):
            projection = None
        intent, plan = None, None
        if review is not None and review.external_subscription_id:
            intents = self.db.query(BillingCheckoutIntent).filter_by(provider=event.provider,
                environment=event.environment, provider_account_id=event.provider_account_id,
                external_subscription_id=review.external_subscription_id, status=BillingIntentStatus.COMPLETED).limit(2).all()
            if len(intents) == 1:
                intent = intents[0]
        if projection:
            try:
                mapping = BillingCatalogService(self.db).resolve_mapping(provider=event.provider,
                    environment=event.environment, provider_account_id=event.provider_account_id,
                    external_product_id=projection.get("product_id"), external_offer_id=projection.get("plan_id"))
                plan = self.db.get(Plan, mapping.plan_id)
            except BillingError:
                pass
        return review, projection, intent, plan

    def _visible(self, event, intent, tenant_id):
        # Existing internal links or a unique completed internal intent only.
        if event.tenant_id is not None:
            return event.tenant_id == tenant_id and (intent is None or intent.tenant_id == tenant_id)
        return intent is not None and intent.tenant_id == tenant_id

    def _blockers(self, event, review, projection, intent, plan):
        now = utc(self.clock())
        blockers = []
        if event.event_type not in {"order_approved", "subscription_renewed"}:
            blockers.append("event_type_not_approvable")
        if event.verification_status != V.MANUAL_REVIEW or event.processing_status != P.PENDING or (review and review.decision):
            blockers.append("event_not_pending_review")
        if event.verification_lease_until and utc(event.verification_lease_until) > now:
            blockers.append("verification_in_progress")
        if intent is None or not self.db.get(Tenant, intent.tenant_id).is_active:
            blockers.append("trusted_tenant_missing")
        if plan is None or (intent and plan.id != intent.plan_id):
            blockers.append("internal_plan_missing_or_mismatched")
        if (review is None or projection is None or review.sale_status != "paid"
            or review.sale_id != projection.get("order_id") or review.product_id != projection.get("product_id")
            or review.external_subscription_id != projection.get("subscription_id")
            or review.external_offer_id != projection.get("plan_id")):
            blockers.append("confirmed_paid_sale_missing")
        if review is None or review.sale_checked_at is None or not now - timedelta(minutes=5) <= utc(review.sale_checked_at) <= now:
            blockers.append("sale_evidence_stale_or_missing")
        if intent and ((event.tenant_id is not None and event.tenant_id != intent.tenant_id)
                       or (event.checkout_intent_id is not None and event.checkout_intent_id != intent.id)):
            blockers.append("internal_binding_mismatch")
        if intent and plan and review:
            sub = self.db.query(Subscription).filter_by(tenant_id=intent.tenant_id).one_or_none()
            if sub and (sub.provider != event.provider or sub.provider_subscription_id != review.external_subscription_id
                        or sub.plan_id != plan.id or sub.status in {S.CANCELED, S.EXPIRED}):
                blockers.append("existing_subscription_binding_mismatch")
            if sub and sub.status != S.INACTIVE and not self._has_period(review, now):
                blockers.append("existing_subscription_requires_trusted_period")
        return blockers

    @staticmethod
    def _has_period(review, now):
        return bool(review and review.period_source == "trusted_subscription_source" and review.period_start
                    and review.period_end and utc(review.period_start) <= now < utc(review.period_end))

    def _read(self, event, context):
        review, projection, intent, plan = context
        projection = projection or {}
        blockers = self._blockers(event, review, projection, intent, plan)
        reason = event.verification_error_code
        return dict(billing_event_id=event.id, provider=event.provider, event_type=event.event_type,
            order_id=projection.get("order_id"), external_subscription_id=projection.get("subscription_id"),
            product_id=projection.get("product_id"), external_offer_id=projection.get("plan_id"),
            candidate_plan_id=plan.id if plan else None, candidate_plan_name=plan.name if plan else None,
            candidate_tenant_id=intent.tenant_id if intent else event.tenant_id,
            verification_status=event.verification_status.value, received_at=event.received_at,
            occurred_at=event.occurred_at, sale_checked_at=review.sale_checked_at if review else None,
            sale_status="paid" if review and review.sale_status == "paid" else None,
            period_start=review.period_start if review else None, period_end=review.period_end if review else None,
            reason=reason if reason in SAFE_REASONS else "verification_requires_review",
            can_approve=not blockers, approval_blockers=blockers,
            access_pending_period=not self._has_period(review, utc(self.clock())),
            decision=review.decision if review else None, decided_by=review.decided_by if review else None,
            decided_at=review.decided_at if review else None,
            rejection_reason=review.rejection_reason if review else None)

    def list(self, user, *, event_type=None, from_date=None, to_date=None, plan_id=None, limit=50, offset=0):
        self._authorize(user)
        # Filter ownership in SQL before pagination; unknown tenant receipts stay
        # quarantined, not disclosed to every tenant administrator.
        owned = self.db.query(BillingManualReview.billing_event_id).join(BillingEvent,
            BillingEvent.id == BillingManualReview.billing_event_id).join(BillingCheckoutIntent, and_(
                BillingCheckoutIntent.provider == BillingEvent.provider,
                BillingCheckoutIntent.environment == BillingEvent.environment,
                BillingCheckoutIntent.provider_account_id == BillingEvent.provider_account_id,
                BillingCheckoutIntent.external_subscription_id == BillingManualReview.external_subscription_id,
                BillingCheckoutIntent.status == BillingIntentStatus.COMPLETED,
                BillingCheckoutIntent.tenant_id == user.tenant_id))
        query = self.db.query(BillingEvent).filter(BillingEvent.provider == "kiwify", BillingEvent.schema_version == 2,
            BillingEvent.verification_status == V.MANUAL_REVIEW,
            or_(BillingEvent.tenant_id == user.tenant_id, BillingEvent.id.in_(owned)))
        if event_type:
            query = query.filter(BillingEvent.event_type == event_type)
        if from_date:
            query = query.filter(BillingEvent.received_at >= from_date)
        if to_date:
            query = query.filter(BillingEvent.received_at <= to_date)
        # Apply ambiguity/plan filters before pagination, with bounded SQL batches.
        results, skipped = [], 0
        for event in query.order_by(BillingEvent.received_at.desc(), BillingEvent.id.desc()).yield_per(100):
            context = self._context(event)
            if not self._visible(event, context[2], user.tenant_id) or (plan_id and (context[3] is None or context[3].id != plan_id)):
                continue
            if skipped < offset:
                skipped += 1
                continue
            results.append(self._read(event, context))
            if len(results) == limit:
                break
        return results

    def _get(self, event_id, user):
        self._authorize(user)
        event = self.db.get(BillingEvent, event_id)
        if event is None or event.provider != "kiwify" or event.schema_version != 2:
            raise ReviewNotFound("review_not_found")
        context = self._context(event)
        if not self._visible(event, context[2], user.tenant_id):
            raise ReviewNotFound("review_not_found")
        return event, context

    def detail(self, event_id, user):
        event, context = self._get(event_id, user)
        return self._read(event, context)

    def decide(self, event_id, user, *, approve, rejection_reason=None):
        try:
            return self._decide(event_id, user, approve=approve, rejection_reason=rejection_reason)
        except OperationalError as exc:
            if getattr(exc.orig, "sqlite_errorcode", None) in {5, 6} or getattr(exc.orig, "sqlstate", None) in {"40001", "40P01"}:
                raise BillingConflict("review_decision_conflict") from None
            raise

    def _decide(self, event_id, user, *, approve, rejection_reason=None):
        now = utc(self.clock())
        with billing_transaction(self.db):
            event, context = self._get(event_id, user)
            review, projection, intent, plan = context
            if event.verification_status != V.MANUAL_REVIEW or event.processing_status != P.PENDING:
                raise BillingConflict("event_not_pending_review")
            if review and review.decision is not None:
                raise BillingConflict("review_already_decided")
            if approve:
                blockers = self._blockers(event, *context)
                if blockers:
                    raise BillingError(blockers[0])
            elif rejection_reason not in REJECTION_REASONS:
                raise BillingError("invalid_rejection_reason")
            # Event-level CAS arbitrates decisions vs worker/another reviewer.
            has_period = approve and self._has_period(review, now)
            claimed = self.db.execute(update(BillingEvent).where(BillingEvent.id == event_id,
                BillingEvent.verification_status == V.MANUAL_REVIEW, BillingEvent.processing_status == P.PENDING,
                ~self.db.query(BillingManualReview.billing_event_id).filter(
                    BillingManualReview.billing_event_id == event_id, BillingManualReview.decision.is_not(None)).exists(),
                or_(BillingEvent.verification_lease_until.is_(None), BillingEvent.verification_lease_until <= now))
                .values(verification_status=V.VERIFIED if has_period else V.MANUAL_REVIEW if approve else V.REJECTED,
                        verification_lease_until=now + timedelta(minutes=2),
                        verified_at=now if has_period else event.verified_at).returning(BillingEvent.id)).scalar_one_or_none()
            if claimed is None:
                raise BillingConflict("review_decision_conflict")
            if review is None:
                review = BillingManualReview(billing_event_id=event_id)
                self.db.add(review)
            elif review.decision is not None:
                raise BillingConflict("review_already_decided")
            self.db.flush()
            decision = "approved" if has_period else "binding_approved" if approve else "rejected"
            decided = self.db.execute(update(BillingManualReview).where(
                BillingManualReview.billing_event_id == event_id, BillingManualReview.decision.is_(None))
                .values(decision=decision, decided_by=user.id, decided_at=now,
                        rejection_reason=None if approve else rejection_reason)
                .returning(BillingManualReview.billing_event_id)).scalar_one_or_none()
            if decided is None:
                raise BillingConflict("review_already_decided")
            if approve:
                actor = SubscriptionActor("user", user.id, "kiwify_manual_review", str(event_id))
                if has_period:
                    proof = VerifiedSubscription(event.provider_account_id, event.environment, review.sale_id,
                        review.external_subscription_id, review.product_id, review.external_offer_id, S.ACTIVE,
                        utc(review.period_start), utc(review.period_end), utc(review.sale_checked_at))
                    KiwifyVerificationService(None, None)._apply(self.db, event, projection, proof, now, actor=actor)
                else:
                    sub = self.db.query(Subscription).filter_by(tenant_id=intent.tenant_id).with_for_update().one_or_none()
                    if sub is None:
                        sub = SubscriptionService(self.db, clock=lambda: now).create_subscription(intent.tenant_id,
                            plan.id, actor=actor, provider="kiwify", provider_subscription_id=review.external_subscription_id)
                    # Never downgrade existing access/status or invent a period.
                    if sub.status != S.INACTIVE or sub.plan_id != plan.id or sub.provider != "kiwify" or sub.provider_subscription_id != review.external_subscription_id:
                        raise BillingError("existing_subscription_requires_trusted_period")
                    if event.subscription_id is not None and event.subscription_id != sub.id:
                        raise BillingError("internal_binding_mismatch")
                    event.tenant_id, event.subscription_id, event.checkout_intent_id = intent.tenant_id, sub.id, intent.id
            event.verification_error_code = "human_approved" if has_period else "manual_review_period_missing" if approve else "human_rejected"
            event.verification_next_at = now + timedelta(hours=1) if approve and not has_period else None
            event.verification_lease_until = event.verification_lease_token = None
            log_admin_action(self.db, tenant_id=user.tenant_id, user_id=user.id, actor_type="user",
                action="billing.manual_review_approved" if has_period else "billing.manual_review_binding_approved" if approve else "billing.manual_review_rejected",
                entity_type="billing_event", entity_id=event_id,
                meta={"billing_event_id": event_id, "reason": review.rejection_reason,
                      "origin": "kiwify_manual_review", "period_source": review.period_source if approve else None,
                      "subscription_id": event.subscription_id, "checkout_intent_id": event.checkout_intent_id,
                      "plan_id": plan.id if approve else None})
            self.db.flush()
            return self._read(event, self._context(event))
