"""Explicit offer mappings and opaque internal intents; no external checkout calls."""
from datetime import datetime, timezone

from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.billing_checkout_intent import BillingCheckoutIntent, BillingIntentStatus as IntentStatus
from app.models.billing_offer_mapping import BillingOfferMapping
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.services.billing_common import BillingConflict, BillingError, billing_transaction, identifier, scope, utc


class BillingCatalogService:
    def __init__(self, db: Session):
        self.db = db

    def create_mapping(self, *, provider: str, environment: str, provider_account_id: str,
                       external_product_id: str, external_offer_id: str, plan_id: int) -> BillingOfferMapping:
        scope(provider, environment)
        for value in (provider_account_id, external_product_id, external_offer_id):
            identifier(value)
        try:
            with billing_transaction(self.db):
                self._plan(plan_id)
                mapping = BillingOfferMapping(provider=provider, environment=environment,
                    provider_account_id=provider_account_id, external_product_id=external_product_id,
                    external_offer_id=external_offer_id, plan_id=plan_id)
                self.db.add(mapping)
                self.db.flush()
                return mapping
        except IntegrityError as exc:
            raise BillingConflict("offer_mapping_conflict") from exc

    def resolve_mapping(self, *, provider: str, environment: str, provider_account_id: str,
                        external_product_id: str, external_offer_id: str) -> BillingOfferMapping:
        scope(provider, environment)
        for value in (provider_account_id, external_product_id, external_offer_id):
            identifier(value)
        mapping = self.db.query(BillingOfferMapping).filter_by(provider=provider, environment=environment,
            provider_account_id=provider_account_id, external_product_id=external_product_id,
            external_offer_id=external_offer_id, active=True).one_or_none()
        if mapping is None:
            raise BillingError("offer_not_mapped")
        self._plan(mapping.plan_id)
        return mapping

    def create_intent(self, tenant_id: int, plan_id: int, *, provider: str, environment: str,
                      provider_account_id: str, expires_at: datetime, now: datetime | None = None) -> BillingCheckoutIntent:
        scope(provider, environment)
        identifier(provider_account_id)
        now = utc(now or datetime.now(timezone.utc))
        end = utc(expires_at)
        if end <= now:
            raise BillingError("intent_expiration_not_future")
        with billing_transaction(self.db):
            if self.db.get(Tenant, tenant_id) is None:
                raise BillingError("tenant_not_found")
            self._plan(plan_id)
            intent = BillingCheckoutIntent(tenant_id=tenant_id, plan_id=plan_id, provider=provider,
                environment=environment, provider_account_id=provider_account_id, expires_at=end)
            self.db.add(intent)
            self.db.flush()
            return intent

    def get_pending_intent(self, tenant_id: int, public_token: str, *, now: datetime | None = None) -> BillingCheckoutIntent:
        identifier(public_token, 64)
        intent = self.db.query(BillingCheckoutIntent).filter_by(tenant_id=tenant_id, public_token=public_token).one_or_none()
        if intent is None:
            raise BillingError("intent_not_found")
        if utc(intent.expires_at) <= utc(now or datetime.now(timezone.utc)):
            raise BillingError("intent_expired")
        if intent.status != IntentStatus.PENDING:
            raise BillingError("intent_not_pending")
        return intent

    def bind_checkout(self, tenant_id: int, public_token: str, external_checkout_id: str, *,
                      now: datetime | None = None) -> BillingCheckoutIntent:
        """Record a future adapter's identifier; this never creates a checkout."""
        now = utc(now or datetime.now(timezone.utc))
        identifier(external_checkout_id)
        try:
            with billing_transaction(self.db):
                intent = self.get_pending_intent(tenant_id, public_token, now=now)
                result = self.db.execute(update(BillingCheckoutIntent).where(
                    BillingCheckoutIntent.id == intent.id, BillingCheckoutIntent.tenant_id == tenant_id,
                    BillingCheckoutIntent.status == IntentStatus.PENDING, BillingCheckoutIntent.expires_at > now,
                    or_(BillingCheckoutIntent.external_checkout_id.is_(None),
                        BillingCheckoutIntent.external_checkout_id == external_checkout_id)
                ).values(external_checkout_id=external_checkout_id).execution_options(synchronize_session=False))
                if result.rowcount != 1:
                    raise BillingConflict("checkout_binding_conflict")
                self.db.refresh(intent)
                return intent
        except IntegrityError as exc:
            raise BillingConflict("checkout_binding_conflict") from exc

    def complete_intent(self, tenant_id: int, public_token: str, *, external_checkout_id: str | None = None,
                        external_customer_id: str | None = None, external_subscription_id: str | None = None,
                        now: datetime | None = None) -> BillingCheckoutIntent:
        now = utc(now or datetime.now(timezone.utc))
        bindings = {"external_checkout_id": external_checkout_id, "external_customer_id": external_customer_id,
                    "external_subscription_id": external_subscription_id}
        for value in bindings.values():
            if value is not None:
                identifier(value)
        try:
            with billing_transaction(self.db):
                intent = self.get_pending_intent(tenant_id, public_token, now=now)
                values = dict(status=IntentStatus.COMPLETED, completed_at=now)
                conditions = [BillingCheckoutIntent.id == intent.id, BillingCheckoutIntent.tenant_id == tenant_id,
                              BillingCheckoutIntent.status == IntentStatus.PENDING, BillingCheckoutIntent.expires_at > now]
                for name, value in bindings.items():
                    if value is not None:
                        column = getattr(BillingCheckoutIntent, name)
                        conditions.append(or_(column.is_(None), column == value))
                        values[name] = value
                result = self.db.execute(update(BillingCheckoutIntent).where(*conditions).values(**values)
                                         .execution_options(synchronize_session=False))
                if result.rowcount != 1:
                    raise BillingConflict("intent_completion_conflict")
                self.db.refresh(intent)
                return intent
        except IntegrityError as exc:
            raise BillingConflict("intent_completion_conflict") from exc

    def expire_intent(self, tenant_id: int, intent_id: int, *, now: datetime | None = None) -> BillingCheckoutIntent:
        now = utc(now or datetime.now(timezone.utc))
        with billing_transaction(self.db):
            result = self.db.execute(update(BillingCheckoutIntent).where(
                BillingCheckoutIntent.id == intent_id, BillingCheckoutIntent.tenant_id == tenant_id,
                BillingCheckoutIntent.status == IntentStatus.PENDING, BillingCheckoutIntent.expires_at <= now
            ).values(status=IntentStatus.EXPIRED).execution_options(synchronize_session=False))
            if result.rowcount != 1:
                raise BillingError("intent_not_due_for_expiration")
            intent = self.db.get(BillingCheckoutIntent, intent_id)
            self.db.refresh(intent)
            return intent

    def _plan(self, plan_id):
        plan = self.db.get(Plan, plan_id)
        if plan is None or not plan.active:
            raise BillingError("plan_not_available")
        return plan
