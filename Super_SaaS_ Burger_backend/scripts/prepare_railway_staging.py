"""Guarded synthetic staging fixtures; no real Kiwify requests or public ingress.

Run only in the dedicated Railway staging service. Connection secrets remain in
Railway environment variables; synthetic user passwords use a hidden TTY prompt.
"""

import argparse
import getpass
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import re
import sys
from uuid import NAMESPACE_URL, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sqlalchemy as sa

ACCOUNT = "phase4-2-synthetic-only"


def validate_target(args, env):
    if not args.confirm_staging:
        raise ValueError("staging_confirmation_required")
    if env.get("ENV") != "staging" or env.get("ENVIRONMENT") != "staging":
        raise ValueError("staging_environment_required")
    for key in (
        "KIWIFY_UNTRUSTED_INGRESS_ENABLED",
        "FEATURE_LEGACY_ADMIN",
        "DEV_BOOTSTRAP_ALLOW",
    ):
        if env.get(key, "").lower() != "false":
            raise ValueError("staging_flags_must_be_explicitly_false")
    if env.get("KIWIFY_API_CLIENT_ID") or env.get("KIWIFY_API_CLIENT_SECRET"):
        raise ValueError("provider_credentials_forbidden_in_synthetic_seed")
    url = sa.engine.make_url(env.get("DATABASE_URL", ""))
    if url.drivername != "postgresql+psycopg":
        raise ValueError("postgresql_psycopg_required")
    if url.host != args.expected_db_host or url.database != args.expected_database:
        raise ValueError("database_target_mismatch")
    if set(url.query) - {"sslmode"}:
        raise ValueError("unexpected_database_url_options")
    if not re.fullmatch(r"[a-z0-9_-]{1,32}", args.batch):
        raise ValueError("invalid_synthetic_batch")
    return url


def reference(value):
    return str(uuid5(NAMESPACE_URL, "fomizero:phase4-2:synthetic:" + value))


def prepare(sessions, password, batch):
    import httpx
    from app.core.kiwify_config import KiwifySettings
    from app.models.admin_user import AdminUser
    from app.models.billing_checkout_intent import BillingCheckoutIntent
    from app.models.billing_manual_review import BillingManualReview
    from app.models.billing_event import BillingEvent, BillingVerificationStatus
    from app.models.plan import Plan
    from app.models.subscription import Subscription, SubscriptionStatus
    from app.models.tenant import Tenant
    from app.services.billing_catalog import BillingCatalogService
    from app.services.billing_common import BillingError
    from app.services.billing_inbox import BillingInboxService
    from app.services.entitlements import EntitlementService
    from app.services.kiwify_api import KiwifySalesAPI
    from app.services.kiwify_projection import project_webhook
    from app.services.kiwify_verification import KiwifyVerificationService
    from app.services.passwords import hash_password
    from app.services.plan_seed import seed_plans
    from app.services.subscriptions import SubscriptionActor, SubscriptionService

    now = datetime.now(timezone.utc)
    # Enables only this injected mock instance, never the application's flags.
    settings = KiwifySettings(
        True, "sandbox", ACCOUNT, "synthetic-client", "synthetic-secret"
    )
    events, tenants = [], {}
    with sessions() as db, db.begin():
        seed_plans(db)
        plan = db.query(Plan).filter_by(code="essential").one()
        catalog = BillingCatalogService(db)
        for label in ("a", "b"):
            slug, name = "phase4-2-" + label, "SYNTHETIC STAGING " + label.upper()
            tenant = db.query(Tenant).filter_by(slug=slug).one_or_none()
            if tenant is None:
                tenant = Tenant(slug=slug, name=name, business_name=name)
                db.add(tenant)
                db.flush()
            if (
                tenant.name != name
                or tenant.business_name != name
                or not tenant.is_active
            ):
                raise ValueError("synthetic_tenant_collision")
            tenants[label] = tenant.id
            roles = ("owner", "admin", "operator") if label == "a" else ("owner",)
            for role in roles:
                email, user_name = (
                    f"{role}-{label}@example.com",
                    f"SYNTHETIC {role} {label}",
                )
                user = (
                    db.query(AdminUser)
                    .filter_by(tenant_id=tenant.id, email=email)
                    .one_or_none()
                )
                if user is None:
                    user = AdminUser(
                        tenant_id=tenant.id,
                        email=email,
                        name=user_name,
                        role=role,
                        password_hash=hash_password(password),
                    )
                    db.add(user)
                elif user.name != user_name or user.role != role or not user.active:
                    raise ValueError("synthetic_user_collision")
                else:
                    user.password_hash = hash_password(password)
            product, offer, external_sub = [
                reference(label + ":" + key)
                for key in ("product", "offer", "subscription")
            ]
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
            sub = db.query(Subscription).filter_by(tenant_id=tenant.id).one_or_none()
            if sub is None:
                sub = SubscriptionService(db).create_subscription(
                    tenant.id,
                    plan.id,
                    provider="kiwify",
                    provider_subscription_id=external_sub,
                    actor=SubscriptionActor("system", origin="synthetic_staging_seed"),
                )
            if (
                sub.status != SubscriptionStatus.INACTIVE
                or sub.current_period_start
                or sub.current_period_end
                or sub.provider_subscription_id != external_sub
                or sub.plan_id != plan.id
            ):
                raise ValueError("synthetic_subscription_not_inactive")
            for action in ("approve", "reject"):
                payload = {
                    "order_id": reference(f"{label}:{batch}:{action}"),
                    "webhook_event_type": "order_approved",
                    "subscription_id": external_sub,
                    "Product": {"product_id": product},
                    "Subscription": {"id": external_sub, "plan": {"id": offer}},
                }
                projection, identity = project_webhook(payload)
                receipt = BillingInboxService(db).receive_event(
                    provider="kiwify",
                    environment="sandbox",
                    provider_account_id=ACCOUNT,
                    provider_event_id=identity,
                    event_type="order_approved",
                    payload=payload,
                    schema_version=2,
                    sanitized_projection=projection,
                )
                events.append((receipt.event.id, payload, label, action))
        db.flush()

    for event_id, payload, _, _ in events:
        with sessions() as db:
            review = db.get(BillingManualReview, event_id)
            if review is not None and review.decision is not None:
                continue  # Never reset/overwrite a human decision.
            refresh = (
                db.get(BillingEvent, event_id).verification_status
                == BillingVerificationStatus.MANUAL_REVIEW
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
                200,
                json={
                    "id": payload["order_id"],
                    "status": "paid",
                    "product": {"id": payload["Product"]["product_id"]},
                },
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
        for tenant_id in tenants.values():
            if EntitlementService(db).evaluate(tenant_id, "orders_monthly").allowed:
                raise ValueError("synthetic_entitlement_must_remain_denied")
        summary = [
            {
                "id": eid,
                "tenant": label,
                "scenario": action,
                "decision": db.get(BillingManualReview, eid).decision,
            }
            for eid, _, label, action in events
        ]
    return {
        "synthetic_only": True,
        "real_provider_calls": False,
        "tenant_ids": tenants,
        "reviews": summary,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-staging", action="store_true")
    for name in ("expected-db-host", "expected-database"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--batch", default="initial")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check-only",
        action="store_true",
        help="Validate configuration without connecting",
    )
    mode.add_argument(
        "--require-empty",
        action="store_true",
        help="Require empty public schema; do not migrate/seed",
    )
    args = parser.parse_args()
    url = validate_target(args, os.environ)
    if args.check_only:
        print(json.dumps({"staging_configuration": "PASS", "database_checked": False}))
        return 0
    from sqlalchemy.orm import sessionmaker
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from app.core.startup_checks import ensure_migrations_applied

    logging.getLogger("httpx").setLevel(logging.WARNING)
    engine = sa.create_engine(url, hide_parameters=True)
    try:
        if args.require_empty:
            with engine.connect() as connection:
                count = connection.execute(
                    sa.text(
                        "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema NOT IN ('pg_catalog', 'information_schema')"
                    )
                ).scalar_one()
                if count:
                    raise ValueError("staging_database_not_empty")
            print(json.dumps({"staging_database_empty": True, "mutated": False}))
            return 0
        root = Path(__file__).resolve().parents[1]
        cfg = Config(str(root / "alembic.ini"))
        if ScriptDirectory.from_config(cfg).get_heads() != [
            "20261007_02_billing_review"
        ]:
            raise ValueError("unexpected_migration_head")
        ensure_migrations_applied(
            engine=engine, alembic_config_path=root / "alembic.ini"
        )
        if not sys.stdin.isatty():
            raise ValueError("interactive_remote_terminal_required")
        password = getpass.getpass("Synthetic staging password (hidden): ")
        if not 20 <= len(password.encode()) <= 72:
            raise ValueError("password_must_have_20_to_72_bytes")
        if password != getpass.getpass("Confirm synthetic password (hidden): "):
            raise ValueError("password_confirmation_mismatch")
        print(
            json.dumps(
                prepare(sessionmaker(bind=engine), password, args.batch), sort_keys=True
            )
        )
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        # Never render SQL/URL/headers/body or secret-bearing exception text.
        print(
            json.dumps({"staging_prepare": "FAIL", "error_class": type(error).__name__})
        )
        sys.exit(1)
