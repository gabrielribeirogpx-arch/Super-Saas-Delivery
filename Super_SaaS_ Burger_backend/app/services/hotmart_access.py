"""New Hotmart contracts require paid access. Existing providers/legacy unaffected."""
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.services.entitlements import EntitlementService


def require_hotmart_order_capacity(db,tenant_id):
    if not isinstance(db,Session):
        return
    sub=db.query(Subscription).filter(Subscription.tenant_id == tenant_id,
        Subscription.provider.in_(("hotmart", "stripe"))).one_or_none()
    if sub is None:
        return
    db.query(Tenant).filter_by(id=tenant_id).with_for_update(key_share=True).one()
    result=EntitlementService(db).evaluate(tenant_id,"orders_monthly")
    if not result.allowed:
        raise HTTPException(403,"A loja precisa regularizar sua assinatura ou o limite de pedidos para receber novos pedidos.")
    from app.models.admin_user import AdminUser
    unverified_owner = db.query(AdminUser.id).filter_by(tenant_id=tenant_id, role="owner", active=True,
        email_verification_required=True, email_verified_at=None).first()
    if unverified_owner:
        raise HTTPException(403,"Confirme o e-mail do proprietário antes de receber pedidos.")


def prepare_signup_subscription(db,tenant_id,provider="hotmart"):
    if provider == "stripe":
        from app.core.stripe_config import stripe_settings
        from app.models.plan import Plan
        from app.services.subscriptions import SubscriptionService
        settings = stripe_settings()
        if not settings.enabled:
            return False
        plan = db.query(Plan).filter_by(code=settings.offers[0].plan_code, active=True).one_or_none()
        if plan is None:
            raise HTTPException(503, "Cadastro de assinaturas temporariamente indisponível")
        SubscriptionService(db).create_subscription(tenant_id, plan.id, provider="stripe")
        return True
    from app.core.hotmart_config import hotmart_settings
    from app.models.plan import Plan
    from app.services.subscriptions import SubscriptionService
    settings=hotmart_settings()
    if not settings.enabled:
        return False
    # Inactive placeholder gives no free access; actual plan selected during checkout.
    plan=db.query(Plan).filter_by(code=settings.offers[0].plan_code,active=True).one_or_none()
    if plan is None:
        raise HTTPException(503,"Cadastro de assinaturas temporariamente indisponível")
    SubscriptionService(db).create_subscription(tenant_id,plan.id,provider="hotmart")
    return True
