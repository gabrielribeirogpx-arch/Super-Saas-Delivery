from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.services import r2_storage


def test_storefront_upload_requires_category(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/storefront/upload",
            params={"tenant_id": "tenant-a"},
            files={"file": ("logo.png", b"image-content", "image/png")},
        )

    assert response.status_code == 422


def test_upload_file_builds_multi_tenant_key(monkeypatch):
    captured = {}

    class FakeClient:
        def upload_fileobj(self, file_obj, bucket_name, object_key):
            captured["bucket_name"] = bucket_name
            captured["object_key"] = object_key
            captured["payload"] = file_obj.read()

    monkeypatch.setenv("R2_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("R2_PUBLIC_URL", "https://cdn.example.com")
    monkeypatch.setattr(r2_storage, "_get_r2_client", lambda: FakeClient())
    monkeypatch.setattr(r2_storage, "uuid4", lambda: SimpleNamespace(hex="fixeduuid"))

    upload = SimpleNamespace(filename="hero.jpg", file=BytesIO(b"abc"))

    file_url = r2_storage.upload_file(
        file=upload,
        tenant_id="tenant-01",
        category="banners",
        subfolder="home",
    )

    assert captured["bucket_name"] == "test-bucket"
    assert captured["object_key"] == "tenants/tenant-01/banners/home/fixeduuid.jpg"
    assert captured["payload"] == b"abc"
    assert file_url == "https://cdn.example.com/tenants/tenant-01/banners/home/fixeduuid.jpg"


def test_storefront_upload_rejects_invalid_mime_type(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/storefront/upload",
            params={"tenant_id": "tenant-a", "category": "banners"},
            files={"file": ("logo.png", b"image-content", "text/plain")},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Tipo de arquivo não permitido."}


def test_storefront_upload_rejects_blocked_extension(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/storefront/upload",
            params={"tenant_id": "tenant-a", "category": "banners"},
            files={"file": ("payload.js", b"console.log('x')", "application/pdf")},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Extensão de arquivo não permitida."}


def test_storefront_upload_rejects_file_above_5mb(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/storefront/upload",
            params={"tenant_id": "tenant-a", "category": "banners"},
            files={"file": ("large.pdf", b"a" * ((5 * 1024 * 1024) + 1), "application/pdf")},
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "Arquivo excede o limite máximo de 5MB."}
