from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from app.deps import require_role
from app.models.admin_user import AdminUser

router = APIRouter(prefix="/api/storefront", tags=["storefront-upload"])

UPLOADS_DIR = Path("uploads")
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024


class UploadResponse(BaseModel):
    url: str


def _resolve_base_url(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")

    if forwarded_host:
        scheme = forwarded_proto or request.url.scheme
        return f"{scheme}://{forwarded_host}"

    return str(request.base_url).rstrip("/")


@router.post("/upload", response_model=UploadResponse)
def upload_storefront_media(
    request: Request,
    file: UploadFile = File(...),
    _user: AdminUser = Depends(require_role(["admin", "owner"])),
):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo inválido")

    content_type = (file.content_type or "").lower()
    if not (content_type.startswith("image/") or content_type.startswith("video/")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de arquivo não suportado",
        )

    upload_bytes = file.file.read(MAX_FILE_SIZE_BYTES + 1)
    if len(upload_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo excede 5MB")

    suffix = Path(file.filename).suffix
    filename = f"{uuid4().hex}{suffix}"

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOADS_DIR / filename
    with path.open("wb") as buffer:
        buffer.write(upload_bytes)

    relative_url = f"/uploads/{filename}"
    public_url = f"{_resolve_base_url(request)}{relative_url}"
    return UploadResponse(url=public_url)
