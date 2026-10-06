"""Read-only commercial evaluation. No operational flow uses this as a guard."""
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.entitlement_features import FEATURE_CODES
from app.models.admin_user import AdminUser
from app.models.order import Order
from app.models.plan import Plan
from app.models.plan_entitlement import PlanEntitlement
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.tenant import Tenant


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@dataclass(frozen=True)
class EntitlementEvaluation:
    allowed: bool
    reason: str
    limit: int | None = None
    usage: int | None = None
    effective_until: datetime | None = None


class EntitlementService:
    def __init__(self, db: Session):
        self.db = db

    def evaluate(self, tenant_id: int, feature_code: str, *, now: datetime | None = None) -> EntitlementEvaluation:
        """Observe capacity for one additional unit; never mutate or enforce.

        `allowed` describes the commercial policy only, not tenant configuration,
        authentication or authorization. Unknown tenants/features are not legacy.
        """
        with self.db.no_autoflush:
            return self._evaluate(tenant_id, feature_code, _utc(now or datetime.now(timezone.utc)))

    def _evaluate(self, tenant_id: int, feature_code: str, now: datetime) -> EntitlementEvaluation:
        if self.db.get(Tenant, tenant_id) is None:
            return EntitlementEvaluation(False, "tenant_not_found")
        if feature_code not in FEATURE_CODES:
            return EntitlementEvaluation(False, "unknown_feature")
        subscription = self.db.query(Subscription).filter_by(tenant_id=tenant_id).one_or_none()
        usage = self._usage(tenant_id, feature_code, now)
        if subscription is None:
            return EntitlementEvaluation(True, "legacy_no_subscription", usage=usage)

        effective_until = None
        status = subscription.status
        if status == SubscriptionStatus.ACTIVE:
            effective_until = _utc(subscription.current_period_end)
        elif status == SubscriptionStatus.TRIALING:
            dates = [_utc(d) for d in (subscription.trial_end, subscription.current_period_end) if d is not None]
            effective_until = min(dates) if dates else None
        elif status == SubscriptionStatus.PAST_DUE:
            effective_until = _utc(subscription.grace_until)
            if effective_until is None:
                return EntitlementEvaluation(False, "subscription_past_due", usage=usage)
        else:
            return EntitlementEvaluation(False, f"subscription_{status.value}", usage=usage)
        if effective_until is not None and now >= effective_until:
            return EntitlementEvaluation(False, "subscription_expired", usage=usage, effective_until=effective_until)
        start = _utc(subscription.current_period_start)
        if start is not None and now < start:
            return EntitlementEvaluation(False, "subscription_not_started", usage=usage, effective_until=effective_until)

        plan = self.db.get(Plan, subscription.plan_id)
        if plan is None or not plan.active:
            return EntitlementEvaluation(False, "plan_inactive", usage=usage, effective_until=effective_until)
        entitlement = self.db.query(PlanEntitlement).filter_by(plan_id=plan.id, feature_code=feature_code).one_or_none()
        if entitlement is None:
            return EntitlementEvaluation(False, "entitlement_missing", usage=usage, effective_until=effective_until)
        expected_reset = "monthly" if feature_code == "orders_monthly" else None
        if entitlement.reset_period != expected_reset:
            return EntitlementEvaluation(False, "unsupported_reset_period", limit=entitlement.limit_value,
                                         usage=usage, effective_until=effective_until)
        result = dict(limit=entitlement.limit_value, usage=usage, effective_until=effective_until)
        if not entitlement.enabled:
            return EntitlementEvaluation(False, "feature_disabled", **result)
        if entitlement.limit_value is not None:
            if usage is None:
                return EntitlementEvaluation(False, "usage_unavailable", **result)
            if usage >= entitlement.limit_value:
                return EntitlementEvaluation(False, "limit_reached", **result)
        return EntitlementEvaluation(True, "entitled", **result)

    def _usage(self, tenant_id: int, feature_code: str, now: datetime) -> int | None:
        if feature_code == "orders_monthly":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
            return self.db.query(Order).filter(Order.tenant_id == tenant_id, Order.created_at >= start,
                                               Order.created_at < end).count()
        if feature_code in {"admin_users", "delivery_users"}:
            query = self.db.query(AdminUser).filter(AdminUser.tenant_id == tenant_id, AdminUser.active.is_(True))
            delivery = func.lower(func.trim(AdminUser.role)) == "delivery"
            return query.filter(delivery if feature_code == "delivery_users" else ~delivery).count()
        return None
