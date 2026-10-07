"""One-shot synthetic review for existing staging tenant; no endpoint or network."""

import argparse
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.prepare_railway_staging import reference, validate_target

ACCOUNT = "phase4-2-meuburger-synthetic-only"


def prepare_single(sessions, expected_tenant_id):
    import httpx
    from app.core.kiwify_config import KiwifySettings
    from app.models.tenant import Tenant
    from app.models.plan import Plan
    from app.models.subscription import Subscription, SubscriptionStatus
    from app.models.billing_checkout_intent import BillingCheckoutIntent
    from app.models.billing_event import BillingEvent, BillingVerificationStatus
    from app.models.billing_manual_review import BillingManualReview
    from app.services.billing_catalog import BillingCatalogService
    from app.services.billing_common import BillingError
    from app.services.billing_inbox import BillingInboxService
    from app.services.subscriptions import SubscriptionService, SubscriptionActor
    from app.services.kiwify_projection import project_webhook
    from app.services.kiwify_api import KiwifySalesAPI
    from app.services.kiwify_verification import KiwifyVerificationService
    from app.services.entitlements import EntitlementService

    now = datetime.now(timezone.utc)
    product, offer, external_sub, sale = [
        reference("single-meuburger:" + k)
        for k in ("product", "offer", "subscription", "sale")
    ]
    payload = {
        "order_id": sale,
        "webhook_event_type": "order_approved",
        "subscription_id": external_sub,
        "Product": {"product_id": product},
        "Subscription": {"id": external_sub, "plan": {"id": offer}},
    }
    projection, identity = project_webhook(payload)
    with sessions() as db, db.begin():
        # Row lock serializes concurrent runs before creating related records.
        tenant = (
            db.query(Tenant)
            .filter_by(id=expected_tenant_id, slug="meuburger")
            .with_for_update()
            .one_or_none()
        )
        if tenant is None or not tenant.is_active:
            raise ValueError("staging_tenant_mismatch")
        plan = db.query(Plan).filter_by(code="essential", active=True).one_or_none()
        if plan is None:
            raise ValueError("seed_plans_required")
        sub = db.query(Subscription).filter_by(tenant_id=tenant.id).one_or_none()
        if sub and (
            sub.status != SubscriptionStatus.INACTIVE
            or sub.current_period_start
            or sub.current_period_end
            or sub.plan_id != plan.id
            or sub.provider != "kiwify"
            or sub.provider_subscription_id != external_sub
        ):
            raise ValueError("existing_subscription_must_not_be_modified")
        # This job must not add a second pending event to this tenant.
        if (
            db.query(BillingEvent)
            .filter(
                BillingEvent.tenant_id == tenant.id,
                BillingEvent.provider_event_id != identity,
                BillingEvent.processing_status == "pending",
            )
            .first()
        ):
            raise ValueError("other_pending_billing_event_exists")
        catalog = BillingCatalogService(db)
        try:
            mapping = catalog.resolve_mapping(
                provider="kiwify",
                environment="sandbox",
                provider_account_id=ACCOUNT,
                external_product_id=product,
                external_offer_id=offer,
            )
            if mapping.plan_id != plan.id:
                raise ValueError("synthetic_mapping_collision")
        except BillingError as error:
            if str(error) != "offer_not_mapped":
                raise
            catalog.create_mapping(
                provider="kiwify",
                environment="sandbox",
                provider_account_id=ACCOUNT,
                external_product_id=product,
                external_offer_id=offer,
                plan_id=plan.id,
            )
        intents = (
            db.query(BillingCheckoutIntent)
            .filter_by(
                provider="kiwify",
                environment="sandbox",
                provider_account_id=ACCOUNT,
                external_subscription_id=external_sub,
            )
            .all()
        )
        if not intents:
            intent = catalog.create_intent(
                tenant.id,
                plan.id,
                provider="kiwify",
                environment="sandbox",
                provider_account_id=ACCOUNT,
                expires_at=now + timedelta(hours=1),
                now=now,
            )
            catalog.complete_intent(
                tenant.id,
                intent.public_token,
                external_subscription_id=external_sub,
                now=now,
            )
        elif (
            len(intents) != 1
            or intents[0].tenant_id != tenant.id
            or intents[0].plan_id != plan.id
            or intents[0].status.value != "completed"
        ):
            raise ValueError("synthetic_intent_collision")
        else:
            intent = intents[0]
        if sub is None:
            sub = SubscriptionService(db).create_subscription(
                tenant.id,
                plan.id,
                provider="kiwify",
                provider_subscription_id=external_sub,
                actor=SubscriptionActor(
                    "system", origin="synthetic_staging_single_review"
                ),
            )
        receipt = BillingInboxService(db).receive_event(
            provider="kiwify",
            environment="sandbox",
            provider_account_id=ACCOUNT,
            provider_event_id=identity,
            event_type="order_approved",
            payload=payload,
            sanitized_projection=projection,
            schema_version=2,
        )
        event = receipt.event
        if (
            event.tenant_id not in (None, tenant.id)
            or event.subscription_id not in (None, sub.id)
            or event.checkout_intent_id not in (None, intent.id)
        ):
            raise ValueError("synthetic_event_collision")
        event.tenant_id, event.subscription_id, event.checkout_intent_id = (
            tenant.id,
            sub.id,
            intent.id,
        )
        event_id = event.id

    with sessions() as db:
        review = db.get(BillingManualReview, event_id)
        decided = review is not None and review.decision is not None
        refresh = (
            db.get(BillingEvent, event_id).verification_status
            == BillingVerificationStatus.MANUAL_REVIEW
        )
    if not decided:
        # The only source is an injected in-memory transport. Flags remain false.
        settings = KiwifySettings(
            True, "sandbox", ACCOUNT, "synthetic-client", "synthetic-secret"
        )

        def response(request):
            if request.url.path.endswith("/oauth/token"):
                return httpx.Response(
                    200,
                    json={
                        "access_token": "synthetic-token",
                        "scope": "sales",
                        "token_type": "Bearer",
                        "expires_in": 86400,
                    },
                )
            return httpx.Response(
                200, json={"id": sale, "status": "paid", "product": {"id": product}}
            )

        source = KiwifySalesAPI(
            settings, reserve=lambda: None, transport=httpx.MockTransport(response)
        )
        try:
            KiwifyVerificationService(sessions, settings, source=source).verify_event(
                event_id, manual_refresh=refresh
            )
        finally:
            source.close()
    with sessions() as db:
        review = db.get(BillingManualReview, event_id)
        event = db.get(BillingEvent, event_id)
        if review is None or (
            not review.decision
            and event.verification_status != BillingVerificationStatus.MANUAL_REVIEW
        ):
            raise ValueError("synthetic_review_not_ready_retry_job")
        if (
            EntitlementService(db)
            .evaluate(expected_tenant_id, "orders_monthly")
            .allowed
        ):
            raise ValueError("synthetic_entitlement_must_remain_denied")
        return {
            "synthetic_only": True,
            "real_provider_calls": False,
            "billing_event_id": event_id,
            "tenant_id": expected_tenant_id,
            "decision": review.decision,
            "verification_status": event.verification_status.value,
            "reason": event.verification_error_code,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-staging", action="store_true")
    parser.add_argument("--expected-db-host", required=True)
    parser.add_argument("--expected-database", required=True)
    parser.add_argument("--expected-tenant-id", required=True, type=int)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    args.batch = "single-meuburger"  # fixed identity; no option to generate more events
    url = validate_target(args, os.environ)
    if args.expected_tenant_id < 1:
        raise ValueError("invalid_tenant_id")
    if args.check_only:
        print(json.dumps({"staging_configuration": "PASS", "database_checked": False}))
        return
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker
    from app.core.startup_checks import ensure_migrations_applied

    logging.getLogger("httpx").setLevel(logging.WARNING)
    engine = sa.create_engine(url, hide_parameters=True)
    try:
        ensure_migrations_applied(
            engine=engine,
            alembic_config_path=Path(__file__).resolve().parents[1] / "alembic.ini",
        )
        print(
            json.dumps(
                prepare_single(sessionmaker(bind=engine), args.expected_tenant_id),
                sort_keys=True,
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            json.dumps({"staging_prepare": "FAIL", "error_class": type(error).__name__})
        )
        sys.exit(1)
