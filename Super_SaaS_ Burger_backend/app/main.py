import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import CORS_ALLOW_ORIGIN_REGEX, CORS_ORIGINS, DATABASE_URL, ENV, FEATURE_LEGACY_ADMIN
from app.core.database import Base, SessionLocal, engine
from app.core.logging_setup import configure_logging
from app.core.startup_checks import ensure_migrations_applied, validate_database_environment
from app.middleware.observability import ObservabilityMiddleware
from app.middleware.admin_session import AdminSessionMiddleware
from app.middleware.tenant_rate_limit import TenantRateLimitMiddleware
from app.middleware.tenant_context import TenantContextMiddleware
import app.models  # garante que os models são importados antes do create_all
import app.services.event_handlers  # registra handlers do event bus

from app.models.admin_user import AdminUser
from app.services.passwords import hash_password
from app.routers.simulator import router as simulator_router
from app.routers.webhook import router as webhook_router
from app.routers.orders import router as orders_router
from app.routers.kds import router as kds_router
from app.routers.delivery import router as delivery_router
from app.routers.settings import router as settings_router
from app.routers.auth import router as auth_router
from app.routers.menu import router as menu_router
from app.routers.menu_categories import router as menu_categories_router
from app.routers.modifiers import router as modifiers_router
from app.routers.admin_auth import router as admin_auth_router
from app.routers.admin_users import router as admin_users_router
from app.routers.admin_audit import router as admin_audit_router
from app.routers.admin_ai import router as admin_ai_router
from app.routers.admin_whatsapp import router as admin_whatsapp_router
from app.routers.admin_menu import legacy_router as admin_menu_legacy_router, router as admin_menu_router
from app.routers.admin_tenant import router as admin_tenant_router
from app.routers.admin import router as admin_router
from app.routers.payments import router as payments_router
from app.routers.finance import router as finance_router
from app.routers.dashboard import router as dashboard_router
from app.routers.inventory import router as inventory_router
from app.routers.reports import router as reports_router
from app.routers.public_menu import legacy_router as public_menu_legacy_router, router as public_menu_router
from app.routers.tickets import router as tickets_router
from app.routers.admin_bootstrap import router as admin_bootstrap_router
from app.routers.onboarding import router as onboarding_router
from app.routers.internal_metrics import router as internal_metrics_router
from app.api.routes.appearance import router as appearance_router
from app.routers.storefront_upload import router as storefront_upload_router

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
configure_logging()

logger = logging.getLogger(__name__)
BOOTSTRAP_PREFIX = "[ADMIN_BOOTSTRAP]"
DEFAULT_ADMIN_EMAIL = "admin@teste.com"
DEFAULT_ADMIN_TENANT_ID = 1
DEFAULT_ADMIN_NAME = "Admin"
DEFAULT_ADMIN_ROLE = "owner"
ENVIRONMENT = os.getenv("ENVIRONMENT", ENV).strip().lower()
RESET_ADMIN_PASSWORD = os.getenv("RESET_ADMIN_PASSWORD", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
REPO_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG_PATH = Path(
    os.getenv("ALEMBIC_CONFIG", str(REPO_ROOT / "alembic.ini"))
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    _startup_tasks()
    yield


app = FastAPI(
    title="Service Delivery API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ObservabilityMiddleware)
app.add_middleware(AdminSessionMiddleware)
app.add_middleware(TenantContextMiddleware)
app.add_middleware(TenantRateLimitMiddleware)

UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


def _password_looks_hashed(password: str) -> bool:
    return password.startswith(("pbkdf2$", "$2a$", "$2b$", "$2y$"))


def _resolve_admin_password_hash(password: str) -> str:
    if _password_looks_hashed(password):
        logger.info("%s password already hashed; storing as-is", BOOTSTRAP_PREFIX)
        return password
    return hash_password(password)


def _ensure_admin_tables_exist() -> None:
    inspector = inspect(engine)
    required_tables = {"admin_users", "admin_login_attempts", "admin_audit_log"}
    missing = [table for table in required_tables if not inspector.has_table(table)]
    if missing:
        logger.error(
            "%s tables missing / migrations not applied missing=%s",
            BOOTSTRAP_PREFIX,
            ",".join(sorted(missing)),
        )
        raise RuntimeError("tables missing / migrations not applied")


def _warn_missing_modifier_active_for_sqlite() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return
    try:
        inspector = inspect(engine)
        if not inspector.has_table("whatsapp_config") or not inspector.has_table("whatsapp_message_log"):
            logger.warning("Run manual migration: migrations/manual_sqlite.sql")
            return
        if not inspector.has_table("modifiers"):
            return
        columns = {column["name"] for column in inspector.get_columns("modifiers")}
        if "active" not in columns:
            logger.warning("Run manual migration: migrations/manual_sqlite.sql")
    except SQLAlchemyError:
        logger.warning("Run manual migration: migrations/manual_sqlite.sql")


def _bootstrap_initial_admin() -> None:
    dev_admin_password = os.getenv("DEV_ADMIN_PASSWORD", "").strip()
    if not dev_admin_password:
        logger.warning("%s skipped: configure DEV_ADMIN_PASSWORD.", BOOTSTRAP_PREFIX)
        return

    dev_admin_email = os.getenv("DEV_ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL).strip() or DEFAULT_ADMIN_EMAIL
    dev_admin_name = os.getenv("DEV_ADMIN_NAME", DEFAULT_ADMIN_NAME).strip() or DEFAULT_ADMIN_NAME
    tenant_id_raw = os.getenv("DEV_ADMIN_TENANT_ID", str(DEFAULT_ADMIN_TENANT_ID)).strip()
    try:
        dev_admin_tenant_id = int(tenant_id_raw)
    except ValueError as exc:
        raise RuntimeError(f"Invalid DEV_ADMIN_TENANT_ID: {tenant_id_raw}") from exc

    logger.info(
        "%s start tenant_id=%s email=%s",
        BOOTSTRAP_PREFIX,
        dev_admin_tenant_id,
        dev_admin_email,
    )

    db = SessionLocal()
    try:
        admin_count = db.query(AdminUser).count()
        logger.info("%s found_admin_count=%s", BOOTSTRAP_PREFIX, admin_count)

        existing_admin = (
            db.query(AdminUser)
            .filter(
                AdminUser.tenant_id == dev_admin_tenant_id,
                AdminUser.email == dev_admin_email,
            )
            .first()
        )
        if existing_admin:
            logger.info(
                "%s exists id=%s tenant_id=%s email=%s",
                BOOTSTRAP_PREFIX,
                existing_admin.id,
                existing_admin.tenant_id,
                existing_admin.email,
            )
            return

        admin = AdminUser(
            tenant_id=dev_admin_tenant_id,
            email=dev_admin_email,
            name=dev_admin_name,
            password_hash=_resolve_admin_password_hash(dev_admin_password),
            role=DEFAULT_ADMIN_ROLE,
            active=True,
        )
        logger.info(
            "%s creating tenant_id=%s email=%s",
            BOOTSTRAP_PREFIX,
            dev_admin_tenant_id,
            dev_admin_email,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        logger.info(
            "%s created success id=%s tenant_id=%s email=%s",
            BOOTSTRAP_PREFIX,
            admin.id,
            admin.tenant_id,
            admin.email,
        )
    except Exception:
        logger.exception("%s ERROR bootstrap failed", BOOTSTRAP_PREFIX)
        raise
    finally:
        db.close()


def _reset_admin_password_if_enabled() -> None:
    if not RESET_ADMIN_PASSWORD:
        logger.info("%s reset disabled", BOOTSTRAP_PREFIX)
        return

    dev_admin_password = os.getenv("DEV_ADMIN_PASSWORD", "").strip()
    if not dev_admin_password:
        logger.info("%s reset enabled but DEV_ADMIN_PASSWORD missing", BOOTSTRAP_PREFIX)
        return

    dev_admin_email = os.getenv("DEV_ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL).strip() or DEFAULT_ADMIN_EMAIL
    tenant_id_raw = os.getenv("DEV_ADMIN_TENANT_ID", str(DEFAULT_ADMIN_TENANT_ID)).strip()
    try:
        dev_admin_tenant_id = int(tenant_id_raw)
    except ValueError as exc:
        raise RuntimeError(f"Invalid DEV_ADMIN_TENANT_ID: {tenant_id_raw}") from exc

    logger.info(
        "%s reset start tenant_id=%s email=%s",
        BOOTSTRAP_PREFIX,
        dev_admin_tenant_id,
        dev_admin_email,
    )

    db = SessionLocal()
    try:
        existing_admin = (
            db.query(AdminUser)
            .filter(
                AdminUser.tenant_id == dev_admin_tenant_id,
                AdminUser.email == dev_admin_email,
            )
            .first()
        )
        if not existing_admin:
            logger.error("%s admin not found for reset", BOOTSTRAP_PREFIX)
            return

        existing_admin.password_hash = hash_password(dev_admin_password)
        db.commit()
        logger.info("%s admin password reset success", BOOTSTRAP_PREFIX)
    except Exception:
        logger.exception("%s reset failed", BOOTSTRAP_PREFIX)
        raise
    finally:
        db.close()


def _startup_tasks() -> None:
    try:
        validate_database_environment()
        if DATABASE_URL.startswith("sqlite"):
            Base.metadata.create_all(bind=engine)
        _warn_missing_modifier_active_for_sqlite()
        ensure_migrations_applied(engine=engine, alembic_config_path=ALEMBIC_CONFIG_PATH)
        _ensure_admin_tables_exist()
        _reset_admin_password_if_enabled()
        _bootstrap_initial_admin()
    except Exception:
        logger.exception("%s ERROR startup failed", BOOTSTRAP_PREFIX)
        raise


# Cria tabelas (dev). Em produção, use migrations.

# Routers
app.include_router(simulator_router)
app.include_router(webhook_router)
app.include_router(orders_router)
app.include_router(kds_router)
app.include_router(delivery_router)
app.include_router(settings_router)
app.include_router(auth_router)
app.include_router(admin_auth_router)
app.include_router(admin_users_router)
app.include_router(admin_audit_router)
app.include_router(admin_ai_router)
app.include_router(admin_whatsapp_router)
app.include_router(admin_menu_router)
app.include_router(admin_menu_legacy_router)
app.include_router(admin_tenant_router)
app.include_router(menu_categories_router)
app.include_router(menu_router)
app.include_router(modifiers_router)
if FEATURE_LEGACY_ADMIN:
    logger.warning("[LEGACY_ADMIN_UI] Enabled via FEATURE_LEGACY_ADMIN=true (deprecated)")
    app.include_router(admin_router)
else:
    logger.info("[LEGACY_ADMIN_UI] Disabled via FEATURE_LEGACY_ADMIN=false")
app.include_router(payments_router)
app.include_router(finance_router)
app.include_router(dashboard_router)
app.include_router(inventory_router)
app.include_router(reports_router)
app.include_router(tickets_router)
app.include_router(admin_bootstrap_router)
app.include_router(public_menu_router)
app.include_router(public_menu_legacy_router)
app.include_router(onboarding_router)
app.include_router(internal_metrics_router)
app.include_router(appearance_router)
app.include_router(storefront_upload_router)


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy"}
