from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.services import r2_storage


def _payload(header: bytes, size: int) -> bytes:
    return header + (b"a" * max(size - len(header), 0))


def _png(size: int) -> bytes:
    return _payload(b"\x89PNG\r\n\x1a\n", size)


def _jpg(size: int) -> bytes:
    return _payload(b"\xff\xd8\xff\xe0", size)


def _pdf(size: int) -> bytes:
    return _payload(b"%PDF-1.7\n", size)


def _mp4(size: int) -> bytes:
    return _payload(b"\x00\x00\x00\x18ftypmp42", size)


def _webm(size: int) -> bytes:
    return _payload(b"\x1a\x45\xdf\xa3", size)


def _client(monkeypatch):
    from app import main
    from app.routers import storefront_upload

    monkeypatch.setattr(main, "_startup_tasks", lambda: None)
    monkeypatch.setattr(storefront_upload, "upload_file", lambda **kwargs: "https://cdn.example.com/uploaded")
    return TestClient(main.app)


def test_storefront_upload_requires_category(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.post(
            "/storefront/upload",
            params={"tenant_id": "tenant-a"},
            files={"file": ("logo.png", _png(128), "image/png")},
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


def test_upload_file_isolates_tenant_keys(monkeypatch):
    keys = []

    class FakeClient:
        def upload_fileobj(self, file_obj, bucket_name, object_key):
            keys.append(object_key)

    monkeypatch.setenv("R2_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("R2_PUBLIC_URL", "https://cdn.example.com")
    monkeypatch.setattr(r2_storage, "_get_r2_client", lambda: FakeClient())
    monkeypatch.setattr(r2_storage, "uuid4", lambda: SimpleNamespace(hex="fixeduuid"))

    r2_storage.upload_file(SimpleNamespace(filename="logo.png", file=BytesIO(b"a")), tenant_id="tenant-a", category="storefront", subfolder="logo")
    r2_storage.upload_file(SimpleNamespace(filename="logo.png", file=BytesIO(b"b")), tenant_id="tenant-b", category="storefront", subfolder="logo")

    assert keys == [
        "tenants/tenant-a/storefront/logo/fixeduuid.png",
        "tenants/tenant-b/storefront/logo/fixeduuid.png",
    ]


def test_storefront_upload_rejects_invalid_mime_type(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.post(
            "/storefront/upload",
            params={"tenant_id": "tenant-a", "category": "storefront", "subfolder": "logo"},
            files={"file": ("logo.png", _png(128), "text/plain")},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Formato de arquivo não suportado."}


def test_storefront_upload_rejects_blocked_extension(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.post(
            "/storefront/upload",
            params={"tenant_id": "tenant-a", "category": "storefront", "subfolder": "logo"},
            files={"file": ("payload.js", b"console.log('x')", "image/png")},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Formato de arquivo não suportado."}


def test_logo_upload_size_limits(monkeypatch):
    with _client(monkeypatch) as client:
        for size in (900 * 1024, 1 * 1024 * 1024):
            response = client.post(
                "/storefront/upload",
                params={"tenant_id": "tenant-a", "category": "storefront", "subfolder": "logo"},
                files={"file": ("logo.png", _png(size), "image/png")},
            )
            assert response.status_code == 200

        response = client.post(
            "/storefront/upload",
            params={"tenant_id": "tenant-a", "category": "storefront", "subfolder": "logo"},
            files={"file": ("logo.png", _png((1 * 1024 * 1024) + 1), "image/png")},
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "A logo excede o limite de 1 MB."}


def test_cover_image_upload_size_limits(monkeypatch):
    with _client(monkeypatch) as client:
        for size in (4 * 1024 * 1024, 5 * 1024 * 1024):
            response = client.post(
                "/storefront/upload",
                params={"tenant_id": "tenant-a", "category": "storefront", "subfolder": "coverImage"},
                files={"file": ("cover.jpg", _jpg(size), "image/jpeg")},
            )
            assert response.status_code == 200

        response = client.post(
            "/storefront/upload",
            params={"tenant_id": "tenant-a", "category": "storefront", "subfolder": "coverImage"},
            files={"file": ("cover.jpg", _jpg((5 * 1024 * 1024) + 1), "image/jpeg")},
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "A imagem de capa excede o limite de 5 MB."}


def test_cover_video_upload_size_limits(monkeypatch):
    with _client(monkeypatch) as client:
        for size in (15 * 1024 * 1024, 20 * 1024 * 1024):
            response = client.post(
                "/storefront/upload",
                params={"tenant_id": "tenant-a", "category": "storefront", "subfolder": "coverVideo"},
                files={"file": ("cover.mp4", _mp4(size), "video/mp4")},
            )
            assert response.status_code == 200

        response = client.post(
            "/storefront/upload",
            params={"tenant_id": "tenant-a", "category": "storefront", "subfolder": "coverVideo"},
            files={"file": ("cover.mp4", _mp4((20 * 1024 * 1024) + 1), "video/mp4")},
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "O vídeo de capa excede o limite de 20 MB."}


def test_storefront_upload_rejects_invalid_types_by_field(monkeypatch):
    with _client(monkeypatch) as client:
        logo_response = client.post(
            "/storefront/upload",
            params={"tenant_id": "tenant-a", "category": "storefront", "subfolder": "logo"},
            files={"file": ("logo.mp4", _mp4(128), "video/mp4")},
        )
        cover_response = client.post(
            "/storefront/upload",
            params={"tenant_id": "tenant-a", "category": "storefront", "subfolder": "coverImage"},
            files={"file": ("cover.webm", _webm(128), "video/webm")},
        )
        video_response = client.post(
            "/storefront/upload",
            params={"tenant_id": "tenant-a", "category": "storefront", "subfolder": "coverVideo"},
            files={"file": ("cover.png", _png(128), "image/png")},
        )

    assert logo_response.status_code == 400
    assert cover_response.status_code == 400
    assert video_response.status_code == 400
    assert logo_response.json() == {"detail": "Formato de arquivo não suportado."}
    assert cover_response.json() == {"detail": "Formato de arquivo não suportado."}
    assert video_response.json() == {"detail": "Formato de arquivo não suportado."}


def test_generic_upload_keeps_existing_pdf_limit(monkeypatch):
    with _client(monkeypatch) as client:
        accepted = client.post(
            "/storefront/upload",
            params={"tenant_id": "tenant-a", "category": "documents"},
            files={"file": ("menu.pdf", _pdf(5 * 1024 * 1024), "application/pdf")},
        )
        rejected = client.post(
            "/storefront/upload",
            params={"tenant_id": "tenant-a", "category": "documents"},
            files={"file": ("large.pdf", _pdf((5 * 1024 * 1024) + 1), "application/pdf")},
        )

    assert accepted.status_code == 200
    assert rejected.status_code == 413
    assert rejected.json() == {"detail": "Arquivo excede o limite máximo de 5 MB."}
