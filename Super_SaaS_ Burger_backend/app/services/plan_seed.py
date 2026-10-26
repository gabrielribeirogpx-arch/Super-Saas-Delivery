"""Explicit, idempotent catalog seed. Never runs during application startup."""
from sqlalchemy.orm import Session

from app.core.entitlement_features import BOOLEAN_FEATURES, NUMERIC_FEATURES
from app.models.plan import Plan
from app.models.plan_entitlement import PlanEntitlement

PLAN_MATRIX = {
    "essential": ("Essencial", (300, 1, 1), (False, False, False, False, False, False, False)),
    "operation": ("Operação", (1500, 3, 5), (True, True, True, True, False, False, False)),
    "pro": ("Pro", (5000, 10, 15), (True, True, True, True, True, True, True)),
}


def seed_plans(db: Session) -> None:
    """Insert missing catalog entries, preserving existing commercial edits.

    Caller owns the transaction. Execute serially as a deployment/admin command.
    """
    for code, (name, limits, flags) in PLAN_MATRIX.items():
        plan = db.query(Plan).filter(Plan.code == code).one_or_none()
        if plan is None:
            plan = Plan(code=code, name=name, active=True)
            db.add(plan)
            db.flush()
        values = [(feature, True, limit) for feature, limit in zip(NUMERIC_FEATURES, limits)]
        values += [(feature, enabled, None) for feature, enabled in zip(BOOLEAN_FEATURES, flags)]
        for feature, enabled, limit in values:
            entry = db.query(PlanEntitlement).filter_by(plan_id=plan.id, feature_code=feature).one_or_none()
            if entry is None:
                db.add(PlanEntitlement(plan_id=plan.id, feature_code=feature, enabled=enabled,
                                       limit_value=limit, reset_period="monthly" if feature == "orders_monthly" else None))
        db.flush()
