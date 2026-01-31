import logging
import os

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

app = FastAPI(title="Super SaaS Burger")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)


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
        logger.warning("Admin bootstrap skipped: configure DEV_ADMIN_PASSWORD.")
        return

    db = SessionLocal()
    try:
        existing_admin = db.query(AdminUser).first()
        if existing_admin:
            logger.info("Admin já existente")
            return

        admin = AdminUser(
            tenant_id=1,
            email="admin@teste.com",
            name="Admin",
            password_hash=hash_password(dev_admin_password),
            role="OWNER",
            active=True,
        )
        db.add(admin)
        db.commit()
        logger.info("Admin bootstrap criado com sucesso")
    finally:
        db.close()


# Cria tabelas (dev). Em produção, depois migramos para Alembic.
Base.metadata.create_all(bind=engine)
_warn_missing_modifier_active_for_sqlite()

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


@app.on_event("startup")
def startup_admin_bootstrap() -> None:
    _bootstrap_initial_admin()


@app.get("/")
def health():
    return {"status": "ok"}
