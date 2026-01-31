import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import CORS_ORIGINS, DATABASE_URL
from app.core.database import Base, SessionLocal, engine
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
from app.routers.admin import router as admin_router
from app.routers.payments import router as payments_router
from app.routers.finance import router as finance_router
from app.routers.dashboard import router as dashboard_router
from app.routers.inventory import router as inventory_router
from app.routers.reports import router as reports_router

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    force=True,
)
for _logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    logging.getLogger(_logger_name).setLevel(LOG_LEVEL)

logger = logging.getLogger(__name__)
BOOTSTRAP_PREFIX = "[ADMIN_BOOTSTRAP]"
DEFAULT_ADMIN_EMAIL = "admin@teste.com"
DEFAULT_ADMIN_TENANT_ID = 1
DEFAULT_ADMIN_NAME = "Admin"
DEFAULT_ADMIN_ROLE = "owner"
RUN_MIGRATIONS_ON_STARTUP = os.getenv("RUN_MIGRATIONS_ON_STARTUP", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
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


app = FastAPI(title="Super SaaS Burger", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


def _run_migrations_if_needed() -> None:
    if not RUN_MIGRATIONS_ON_STARTUP:
        return
    if not ALEMBIC_CONFIG_PATH.exists():
        logger.error(
            "%s ERROR alembic config not found path=%s",
            BOOTSTRAP_PREFIX,
            ALEMBIC_CONFIG_PATH,
        )
        raise RuntimeError("alembic config not found")

    logger.info("%s running migrations", BOOTSTRAP_PREFIX)
    try:
        config = Config(str(ALEMBIC_CONFIG_PATH))
        config.set_main_option("sqlalchemy.url", DATABASE_URL)
        command.upgrade(config, "head")
    except Exception:
        logger.exception("%s ERROR migrations failed", BOOTSTRAP_PREFIX)
        raise


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
        if DATABASE_URL.startswith("sqlite"):
            Base.metadata.create_all(bind=engine)
        _warn_missing_modifier_active_for_sqlite()
        _run_migrations_if_needed()
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
app.include_router(menu_categories_router)
app.include_router(menu_router)
app.include_router(modifiers_router)
app.include_router(admin_router)
app.include_router(payments_router)
app.include_router(finance_router)
app.include_router(dashboard_router)
app.include_router(inventory_router)
app.include_router(reports_router)


@app.get("/")
def health():
    return {"status": "ok"}
