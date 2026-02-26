from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.appearance import router as appearance_router
from app.core.database import get_db
from app.deps import get_current_user
from app.models.tenant import Tenant
from app.models.tenant_public_settings import TenantPublicSettings


class _FakeQuery:
    def __init__(self, db):
        self._db = db

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._db.settings


class _FakeDb:
    def __init__(self):
        self.settings = None
        self.tenant = SimpleNamespace(id=7, banner_blur_enabled=True)

    def query(self, model):
        if model == TenantPublicSettings:
            return _FakeQuery(self)
        if model == Tenant:
            return _FakeQuery(SimpleNamespace(settings=self.tenant))
        raise AssertionError("Unexpected model queried")

    def add(self, row):
        self.settings = row

    def commit(self):
        return None

    def refresh(self, _row):
        return None


def _build_client(db):
    app = FastAPI()
    app.include_router(appearance_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(tenant_id=7)
    return TestClient(app)


def test_get_appearance_returns_defaults_when_not_configured():
    client = _build_client(_FakeDb())

    response = client.get("/api/appearance")

    assert response.status_code == 200
    assert response.json() == {
        "primary_color": "#2563eb",
        "secondary_color": "#111827",
        "button_radius": 12,
        "hero_image_url": None,
        "logo_url": None,
        "font_family": "Inter",
        "layout_variant": "clean",
        "banner_blur_enabled": True,
    }


def test_put_appearance_persists_and_returns_payload():
    db = _FakeDb()
    client = _build_client(db)
    payload = {
        "primary_color": "#ff0000",
        "secondary_color": "#00ff00",
        "button_radius": 20,
        "hero_image_url": "https://cdn.example.com/hero.png",
        "logo_url": "https://cdn.example.com/logo.png",
        "font_family": "Roboto",
        "layout_variant": "modern",
        "banner_blur_enabled": False,
    }

    put_response = client.put("/api/appearance", json=payload)
    get_response = client.get("/api/appearance")

    assert put_response.status_code == 200
    assert put_response.json() == payload
    assert get_response.status_code == 200
    assert get_response.json() == payload
