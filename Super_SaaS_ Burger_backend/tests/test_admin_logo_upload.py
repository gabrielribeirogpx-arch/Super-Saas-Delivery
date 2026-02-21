from io import BytesIO
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.models.tenant_public_settings import TenantPublicSettings
from app.routers import admin_upload


class _FakeQuery:
    def __init__(self, db):
        self._db = db

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._db.settings


class _FakeDb:
    def __init__(self, settings=None):
        self.settings = settings
        self.did_commit = False

    def query(self, model):
        if model is TenantPublicSettings:
            return _FakeQuery(self)
        raise AssertionError("Unexpected model queried")

    def add(self, row):
        self.settings = row

    def commit(self):
        self.did_commit = True


def _build_client(db):
    app = FastAPI()
    app.include_router(admin_upload.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[admin_upload.ADMIN_UPLOAD_ACCESS] = lambda: SimpleNamespace(
        tenant_id=1,
        role="owner",
    )
    return TestClient(app)


def test_admin_logo_upload_persists_logo_url(monkeypatch):
    db = _FakeDb()
    client = _build_client(db)
    captured = {}

    def _fake_upload_file(*, file, tenant_id, category, subfolder):
        captured["tenant_id"] = tenant_id
        captured["category"] = category
        captured["subfolder"] = subfolder
        captured["filename"] = file.filename
        return "https://cdn.example.com/tenants/7/branding/logo/new-logo.png"

    monkeypatch.setattr(admin_upload, "upload_file", _fake_upload_file)

    response = client.post(
        "/api/admin/7/upload/logo",
        files={"file": ("logo.png", b"png-bytes", "image/png")},
    )

    assert response.status_code == 200
    assert response.json() == {"logo_url": "https://cdn.example.com/tenants/7/branding/logo/new-logo.png"}
    assert captured == {
        "tenant_id": "7",
        "category": "branding",
        "subfolder": "logo",
        "filename": "logo.png",
    }
    assert db.settings is not None
    assert db.settings.tenant_id == 7
    assert db.settings.logo_url == "https://cdn.example.com/tenants/7/branding/logo/new-logo.png"
    assert db.did_commit is True


def test_admin_logo_upload_updates_existing_settings(monkeypatch):
    existing = TenantPublicSettings(tenant_id=5)
    existing.logo_url = "https://old.example.com/logo.png"
    db = _FakeDb(settings=existing)
    client = _build_client(db)

    monkeypatch.setattr(
        admin_upload,
        "upload_file",
        lambda **_kwargs: "https://cdn.example.com/tenants/5/branding/logo/new-logo.png",
    )

    response = client.post(
        "/api/admin/5/upload/logo",
        files={"file": ("logo.webp", BytesIO(b"img").read(), "image/webp")},
    )

    assert response.status_code == 200
    assert response.json() == {"logo_url": "https://cdn.example.com/tenants/5/branding/logo/new-logo.png"}
    assert db.settings is existing
    assert existing.logo_url == "https://cdn.example.com/tenants/5/branding/logo/new-logo.png"
    assert db.did_commit is True
