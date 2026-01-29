import logging

from fastapi import FastAPI
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import DATABASE_URL, DEV_BOOTSTRAP_ALLOW, IS_DEV
from app.core.database import Base, SessionLocal, engine
import app.models  # garante que os models são importados antes do create_all
import app.services.event_handlers  # registra handlers do event bus

from app.models.admin_user import AdminUser
from app.models.tenant import Tenant
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
from app.routers.admin_bootstrap import router as admin_bootstrap_router
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


def _bootstrap_dev_admin_users() -> None:
    if not IS_DEV:
        return
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).all()
        for tenant in tenants:
            existing = (
                db.query(AdminUser)
                .filter(AdminUser.tenant_id == tenant.id)
                .first()
            )
            if existing:
                continue
            admin = AdminUser(
                tenant_id=tenant.id,
                email="admin@local",
                name="Admin",
                password_hash=hash_password("admin123"),
                role="admin",
                active=True,
            )
            db.add(admin)
            db.commit()
            print(f"DEV ADMIN CREATED: admin@local / admin123 (tenant {tenant.id}) - troque a senha.")
    finally:
        db.close()


# Cria tabelas (dev). Em produção, depois migramos para Alembic.
Base.metadata.create_all(bind=engine)
_warn_missing_modifier_active_for_sqlite()
_bootstrap_dev_admin_users()

# Routers
app.include_router(simulator_router)
app.include_router(webhook_router)
app.include_router(orders_router)
app.include_router(kds_router)
app.include_router(delivery_router)
app.include_router(settings_router)
app.include_router(auth_router)
app.include_router(admin_auth_router)
if IS_DEV and DEV_BOOTSTRAP_ALLOW:
    app.include_router(admin_bootstrap_router)
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
