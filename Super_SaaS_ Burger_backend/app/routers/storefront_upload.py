import hashlib
import hmac
import os
from pathlib import Path

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile

from app.services.r2_storage import upload_driver_apk, upload_file

router = APIRouter()

MB = 1024 * 1024
DEFAULT_MAX_FILE_SIZE_BYTES = 5 * MB
STOREFRONT_UPLOAD_RULES = {
    "logo": {
        "max_size": 1 * MB,
        "allowed_mime_types": {"image/png", "image/jpeg", "image/webp"},
        "allowed_extensions": {"png", "jpg", "jpeg", "webp"},
        "size_error": "A logo excede o limite de 1 MB.",
    },
    "coverImage": {
        "max_size": 5 * MB,
        "allowed_mime_types": {"image/png", "image/jpeg", "image/webp"},
        "allowed_extensions": {"png", "jpg", "jpeg", "webp"},
        "size_error": "A imagem de capa excede o limite de 5 MB.",
    },
    "coverVideo": {
        "max_size": 20 * MB,
        "allowed_mime_types": {"video/mp4", "video/webm"},
        "allowed_extensions": {"mp4", "webm"},
        "size_error": "O vídeo de capa excede o limite de 20 MB.",
    },
}
ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "video/mp4",
    "video/webm",
    "application/pdf",
}
ALLOWED_EXTENSIONS_BY_MIME_TYPE = {
    "image/png": {"png"},
    "image/jpeg": {"jpg", "jpeg"},
    "image/webp": {"webp"},
    "video/mp4": {"mp4"},
    "video/webm": {"webm"},
    "application/pdf": {"pdf"},
}
BLOCKED_EXTENSIONS = {"exe", "bat", "sh", "js", "php", "py", "zip", "rar"}
DRIVER_APK_VERSION = "1.0.2"
DRIVER_APK_SHA256 = "41e0b8ba7a2a83ce563857e7ecf56b9ce1adfc043e3c10758897840b7df077c9"
DRIVER_APK_MAX_SIZE_BYTES = 110 * MB


def _read_header(file: UploadFile, length: int = 16) -> bytes:
    current_pos = file.file.tell()
    file.file.seek(0)
    header = file.file.read(length)
    file.file.seek(current_pos)
    return header


def _content_matches_mime_type(file: UploadFile, mime_type: str) -> bool:
    header = _read_header(file, 16)
    if mime_type == "image/png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/jpeg":
        return header.startswith(b"\xff\xd8\xff")
    if mime_type == "image/webp":
        return header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    if mime_type == "application/pdf":
        return header.startswith(b"%PDF-")
    if mime_type == "video/mp4":
        return len(header) >= 12 and header[4:8] == b"ftyp"
    if mime_type == "video/webm":
        return header.startswith(b"\x1a\x45\xdf\xa3")
    return False


def _get_file_size(file: UploadFile) -> int:
    current_pos = file.file.tell()
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(current_pos)
    return file_size


def _validate_upload(file: UploadFile, *, category: str, subfolder: str | None = None) -> None:
    extension = Path(file.filename or "").suffix.lower().lstrip(".")
    if not extension or extension in BLOCKED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Formato de arquivo não suportado.")

    rules = STOREFRONT_UPLOAD_RULES.get(subfolder or "") if category == "storefront" else None
    allowed_mime_types = rules["allowed_mime_types"] if rules else ALLOWED_MIME_TYPES
    allowed_extensions = rules["allowed_extensions"] if rules else ALLOWED_EXTENSIONS_BY_MIME_TYPE.get(file.content_type or "", set())

    if file.content_type not in allowed_mime_types or extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Formato de arquivo não suportado.")

    if not _content_matches_mime_type(file, file.content_type or ""):
        raise HTTPException(status_code=400, detail="Formato de arquivo não suportado.")

    max_size = rules["max_size"] if rules else DEFAULT_MAX_FILE_SIZE_BYTES
    if _get_file_size(file) > max_size:
        detail = rules["size_error"] if rules else "Arquivo excede o limite máximo de 5 MB."
        raise HTTPException(status_code=413, detail=detail)


@router.post("/storefront/upload")
def upload_storefront_file(
    file: UploadFile = File(...),
    tenant_id: str = Query(...),
    category: str = Query(...),
    subfolder: str | None = Query(default=None),
):
    try:
        _validate_upload(file, category=category, subfolder=subfolder)
        file_url = upload_file(
            file=file,
            tenant_id=tenant_id,
            category=category,
            subfolder=subfolder,
        )
        return {"url": file_url}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Erro ao enviar arquivo.") from exc


@router.post("/internal/releases/driver-apk-1-0-2")
def upload_driver_release(
    file: UploadFile = File(...),
    release_token: str = Header(default="", alias="X-Release-Upload-Token"),
):
    expected_token = os.getenv("DRIVER_RELEASE_UPLOAD_TOKEN", "")
    if not expected_token or not hmac.compare_digest(release_token, expected_token):
        raise HTTPException(status_code=404, detail="Não encontrado.")

    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size <= 0 or size > DRIVER_APK_MAX_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="APK fora do tamanho permitido.")

    digest = hashlib.sha256()
    header = file.file.read(4)
    if header != b"PK\x03\x04":
        raise HTTPException(status_code=400, detail="Arquivo APK inválido.")
    digest.update(header)
    while chunk := file.file.read(1024 * 1024):
        digest.update(chunk)
    file.file.seek(0)

    if not hmac.compare_digest(digest.hexdigest(), DRIVER_APK_SHA256):
        raise HTTPException(status_code=400, detail="Assinatura de conteúdo inválida.")

    try:
        url = upload_driver_apk(file=file, version=DRIVER_APK_VERSION)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Erro ao publicar APK.") from exc

    return {"url": url, "version": DRIVER_APK_VERSION, "sha256": DRIVER_APK_SHA256}
