import logging

from fastapi import FastAPI
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import DATABASE_URL
from app.core.database import Base, engine
import app.models  # garante que os models são importados antes do create_all

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
from app.routers.admin import router as admin_router
from app.routers.payments import router as payments_router
from app.routers.finance import router as finance_router
from app.routers.dashboard import router as dashboard_router
from app.routers.inventory import router as inventory_router

app = FastAPI(title="Super SaaS Burger")

logger = logging.getLogger(__name__)


def _warn_missing_modifier_active_for_sqlite() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return
    try:
        inspector = inspect(engine)
        if not inspector.has_table("modifiers"):
            return
        columns = {column["name"] for column in inspector.get_columns("modifiers")}
        if "active" not in columns:
            logger.warning("Run manual migration: migrations/manual_sqlite.sql")
    except SQLAlchemyError:
        logger.warning("Run manual migration: migrations/manual_sqlite.sql")


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
app.include_router(menu_categories_router)
app.include_router(menu_router)
app.include_router(modifiers_router)
app.include_router(admin_router)
app.include_router(payments_router)
app.include_router(finance_router)
app.include_router(dashboard_router)
app.include_router(inventory_router)

@app.get("/")
def health():
    return {"status": "ok"}
