"""Commercial guards for Hotmart contracts; RBAC and tenant checks remain required."""
from dataclasses import asdict
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.entitlement_features import FEATURE_CODES
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.services.entitlements import EntitlementService


def is_managed(db, tenant_id):
    return isinstance(db, Session) and db.query(Subscription.id).filter_by(
        tenant_id=tenant_id, provider="hotmart").first() is not None


def feature_allowed(db, tenant_id, feature):
    if feature not in FEATURE_CODES:
        return False
    if not is_managed(db, tenant_id):
        return True
    return EntitlementService(db).evaluate(tenant_id, feature).allowed


def require_feature(db, tenant_id, feature):
    if not feature_allowed(db, tenant_id, feature):
        result = EntitlementService(db).evaluate(tenant_id, feature)
        raise HTTPException(403, detail={"code": "subscription_required", "feature": feature,
            "reason": result.reason, "limit": result.limit, "usage": result.usage,
            "message": "Regularize sua assinatura ou escolha um plano que inclua este recurso."})


def require_user_capacity(db, tenant_id, *, role, active=True, target=None):
    if not is_managed(db, tenant_id):
        return
    # Held through the caller's commit: all create/reactivate/role-change paths
    # serialize on the same tenant before counting active seats in PostgreSQL.
    db.query(Tenant).filter_by(id=tenant_id).with_for_update().one()
    if target is not None:
        db.refresh(target)
        role = target.role if role is None else role
        active = target.active if active is None else active
    if not active:
        return  # reductions and account recovery remain possible after expiry
    feature = "delivery_users" if role.strip().lower() == "delivery" else "admin_users"
    if target is not None and target.active:
        old = "delivery_users" if target.role.strip().lower() == "delivery" else "admin_users"
        if old == feature:
            return  # editing an occupied seat does not consume another seat
    require_feature(db, tenant_id, feature)


def access_summary(db, tenant_id):
    managed = is_managed(db, tenant_id)
    features = {feature: asdict(EntitlementService(db).evaluate(tenant_id, feature))
                for feature in sorted(FEATURE_CODES)} if managed else {}
    # An exhausted order quota does not expire the subscription or other features.
    active = not managed or features["orders_monthly"]["reason"] in {"entitled", "limit_reached"}
    return {"managed": managed, "active": active, "features": features}
