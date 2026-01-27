from fastapi import FastAPI

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

app = FastAPI(title="Super SaaS Burger")

# Cria tabelas (dev). Em produção, depois migramos para Alembic.
Base.metadata.create_all(bind=engine)

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

@app.get("/")
def health():
    return {"status": "ok"}
