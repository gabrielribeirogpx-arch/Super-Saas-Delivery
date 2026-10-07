"""Tenant-scoped subscription lifecycle. No provider-specific business rules."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.models.admin_user import AdminUser
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionStatus as Status
from app.models.tenant import Tenant
from app.services.admin_audit import log_admin_action
from app.services.billing_common import BillingConflict, BillingError, billing_transaction, identifier, utc


VALID_TRANSITIONS = {
    Status.INACTIVE: frozenset({Status.TRIALING, Status.ACTIVE, Status.CANCELED}),
    Status.TRIALING: frozenset({Status.ACTIVE, Status.CANCELED, Status.EXPIRED}),
    Status.ACTIVE: frozenset({Status.PAST_DUE, Status.CANCELED, Status.EXPIRED}),
    Status.PAST_DUE: frozenset({Status.ACTIVE, Status.CANCELED, Status.EXPIRED}),
    Status.CANCELED: frozenset({Status.EXPIRED}),
    Status.EXPIRED: frozenset(),
}


@dataclass(frozen=True)
class SubscriptionActor:
    actor_type: str = "system"
    user_id: int | None = None
    origin: str = "internal"
    correlation_id: str | None = None


class SubscriptionService:
    def __init__(self, db: Session, *, clock: Callable[[], datetime] | None = None):
        self.db = db
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def create_subscription(
        self, tenant_id: int, plan_id: int, *, actor: SubscriptionActor | None = None,
        provider: str | None = None, provider_subscription_id: str | None = None,
        provider_customer_id: str | None = None,
    ) -> Subscription:
        actor = actor or SubscriptionActor()
        try:
            with billing_transaction(self.db):
                self._validate_actor(tenant_id, actor)
                self._plan(plan_id)
                if provider is not None:
                    identifier(provider, 50)
                elif provider_subscription_id is not None or provider_customer_id is not None:
                    raise BillingError("external_ids_require_provider")
                for external_id in (provider_subscription_id, provider_customer_id):
                    if external_id is not None:
                        identifier(external_id)
                sub = Subscription(tenant_id=tenant_id, plan_id=plan_id, provider=provider,
                                   provider_subscription_id=provider_subscription_id,
                                   provider_customer_id=provider_customer_id, status=Status.INACTIVE)
                self.db.add(sub)
                # The unique tenant constraint is the arbiter, not a preceding SELECT.
                self.db.flush()
                self._audit(sub, "subscription.created", None, actor)
                self.db.flush()
                return sub
        except IntegrityError as exc:
            raise BillingConflict("subscription_creation_conflict") from exc

    def start_trial(self, tenant_id: int, subscription_id: int, *, trial_end: datetime,
                    actor: SubscriptionActor | None = None, expected_version: int | None = None) -> Subscription:
        def mutate(sub, now):
            self._transition(sub, Status.TRIALING)
            end = utc(trial_end)
            if end <= now:
                raise BillingError("trial_end_not_future")
            sub.current_period_start = now
            sub.current_period_end = end
            sub.trial_end = end
        return self._apply(tenant_id, subscription_id, "subscription.trial_started", mutate, actor, expected_version)

    def activate_subscription(
        self, tenant_id: int, subscription_id: int, *, current_period_end: datetime,
        current_period_start: datetime | None = None, actor: SubscriptionActor | None = None,
        expected_version: int | None = None,
    ) -> Subscription:
        def mutate(sub, now):
            self._transition(sub, Status.ACTIVE)
            start = utc(current_period_start) if current_period_start is not None else now
            end = utc(current_period_end)
            if start > now or end <= now or end <= start:
                raise BillingError("invalid_active_period")
            self._plan(sub.plan_id)
            sub.current_period_start = start
            sub.current_period_end = end
            sub.trial_end = None
            sub.past_due_since = None
            sub.grace_until = None
        return self._apply(tenant_id, subscription_id, "subscription.activated", mutate, actor, expected_version)

    def renew_subscription(self, tenant_id: int, subscription_id: int, *, current_period_start: datetime,
                           current_period_end: datetime, actor: SubscriptionActor | None = None,
                           expected_version: int | None = None) -> Subscription:
        def mutate(sub, now):
            start, end = utc(current_period_start), utc(current_period_end)
            if sub.status != Status.ACTIVE or sub.current_period_end is None:
                raise BillingError("invalid_renewal_state")
            if start > now or end <= now or end <= start or end <= utc(sub.current_period_end):
                raise BillingError("invalid_renewal_period")
            self._plan(sub.plan_id)
            sub.current_period_start, sub.current_period_end = start, end
        return self._apply(tenant_id, subscription_id, "subscription.renewed", mutate, actor, expected_version)

    def mark_past_due(self, tenant_id: int, subscription_id: int, *, grace_until: datetime | None = None,
                      actor: SubscriptionActor | None = None, expected_version: int | None = None) -> Subscription:
        def mutate(sub, now):
            self._transition(sub, Status.PAST_DUE)
            grace = utc(grace_until) if grace_until is not None else None
            if grace is not None and grace <= now:
                raise BillingError("grace_not_future")
            sub.past_due_since = now
            sub.grace_until = grace
        return self._apply(tenant_id, subscription_id, "subscription.past_due", mutate, actor, expected_version)

    def schedule_cancellation(self, tenant_id: int, subscription_id: int, *, actor: SubscriptionActor | None = None,
                              expected_version: int | None = None) -> Subscription:
        def mutate(sub, now):
            if sub.status not in {Status.TRIALING, Status.ACTIVE, Status.PAST_DUE}:
                raise BillingError("invalid_cancellation_state")
            end = self._effective_end(sub)
            if end is None or end <= now:
                raise BillingError("cancellation_period_not_future")
            if sub.cancel_at_period_end:
                raise BillingError("cancellation_already_scheduled")
            sub.cancel_at_period_end = True
        return self._apply(tenant_id, subscription_id, "subscription.cancellation_scheduled", mutate, actor, expected_version)

    def cancel_subscription(self, tenant_id: int, subscription_id: int, *, actor: SubscriptionActor | None = None,
                            expected_version: int | None = None) -> Subscription:
        def mutate(sub, now):
            self._transition(sub, Status.CANCELED)
            sub.canceled_at = now
            sub.cancel_at_period_end = False
            sub.grace_until = None
        return self._apply(tenant_id, subscription_id, "subscription.canceled", mutate, actor, expected_version)

    def expire_subscription(self, tenant_id: int, subscription_id: int, *, actor: SubscriptionActor | None = None,
                            expected_version: int | None = None) -> Subscription:
        def mutate(sub, now):
            end = utc(sub.canceled_at) if sub.status == Status.CANCELED and sub.canceled_at else self._effective_end(sub)
            if end is None or end > now:
                raise BillingError("subscription_not_due_for_expiration")
            self._transition(sub, Status.EXPIRED)
            sub.cancel_at_period_end = False
        return self._apply(tenant_id, subscription_id, "subscription.expired", mutate, actor, expected_version)

    def change_plan(self, tenant_id: int, subscription_id: int, plan_id: int, *, actor: SubscriptionActor | None = None,
                    expected_version: int | None = None) -> Subscription:
        def mutate(sub, now):
            if sub.status in {Status.CANCELED, Status.EXPIRED}:
                raise BillingError("terminal_subscription")
            if sub.plan_id == plan_id:
                raise BillingError("plan_unchanged")
            self._plan(plan_id)
            sub.plan_id = plan_id
        return self._apply(tenant_id, subscription_id, "subscription.plan_changed", mutate, actor, expected_version)

    def _apply(self, tenant_id, subscription_id, action, mutate, actor, expected_version):
        actor = actor or SubscriptionActor()
        try:
            with billing_transaction(self.db):
                self._validate_actor(tenant_id, actor)
                sub = (self.db.query(Subscription).filter_by(id=subscription_id, tenant_id=tenant_id)
                       .populate_existing().with_for_update().one_or_none())
                if sub is None:
                    raise BillingError("subscription_not_found")
                if expected_version is not None and sub.version != expected_version:
                    raise BillingConflict("stale_subscription_version")
                before = self._snapshot(sub)
                mutate(sub, utc(self.clock()))
                # Versioned UPDATE prevents a lost update even without SQLite row locks.
                self.db.flush()
                self._audit(sub, action, before, actor)
                self.db.flush()
                return sub
        except StaleDataError as exc:
            raise BillingConflict("concurrent_subscription_transition") from exc

    def _validate_actor(self, tenant_id: int, actor: SubscriptionActor):
        if self.db.get(Tenant, tenant_id) is None:
            raise BillingError("tenant_not_found")
        identifier(actor.origin, 100)
        if actor.correlation_id is not None:
            identifier(actor.correlation_id, 255)
        if actor.actor_type not in {"user", "system", "provider"}:
            raise BillingError("invalid_actor")
        if actor.actor_type == "user":
            user = self.db.get(AdminUser, actor.user_id) if actor.user_id is not None else None
            if user is None or user.tenant_id != tenant_id or not user.active:
                raise BillingError("invalid_human_actor")
        elif actor.user_id is not None:
            raise BillingError("automatic_actor_has_user")

    def _plan(self, plan_id):
        plan = self.db.get(Plan, plan_id)
        if plan is None or not plan.active:
            raise BillingError("plan_not_available")
        return plan

    @staticmethod
    def _transition(sub, target):
        if target not in VALID_TRANSITIONS[sub.status]:
            raise BillingError("invalid_subscription_transition")
        sub.status = target

    @staticmethod
    def _effective_end(sub):
        if sub.status == Status.PAST_DUE and sub.grace_until is not None:
            return utc(sub.grace_until)
        dates = [utc(sub.current_period_end)] if sub.current_period_end is not None else []
        if sub.status == Status.TRIALING and sub.trial_end is not None:
            dates.append(utc(sub.trial_end))
        return min(dates) if dates else None

    @staticmethod
    def _snapshot(sub):
        return {"status": sub.status.value, "plan_id": sub.plan_id, "version": sub.version,
                "current_period_start": utc(sub.current_period_start).isoformat() if sub.current_period_start else None,
                "current_period_end": utc(sub.current_period_end).isoformat() if sub.current_period_end else None,
                "trial_end": utc(sub.trial_end).isoformat() if sub.trial_end else None,
                "canceled_at": utc(sub.canceled_at).isoformat() if sub.canceled_at else None,
                "cancel_at_period_end": sub.cancel_at_period_end,
                "past_due_since": utc(sub.past_due_since).isoformat() if sub.past_due_since else None,
                "grace_until": utc(sub.grace_until).isoformat() if sub.grace_until else None}

    def _audit(self, sub, action, before, actor):
        log_admin_action(self.db, tenant_id=sub.tenant_id, user_id=actor.user_id, actor_type=actor.actor_type,
                         action=action, entity_type="subscription", entity_id=sub.id,
                         meta={"subscription_id": sub.id, "origin": actor.origin, "correlation_id": actor.correlation_id,
                               "before": before, "after": self._snapshot(sub),
                               "previous_plan_id": before["plan_id"] if before else None, "new_plan_id": sub.plan_id})
