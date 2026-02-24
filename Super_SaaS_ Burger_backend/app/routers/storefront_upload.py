from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.services.r2_storage import upload_file

router = APIRouter()

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "video/mp4",
    "video/webm",
    "application/pdf",
}
BLOCKED_EXTENSIONS = {"exe", "bat", "sh", "js", "php", "py", "zip", "rar"}


def _validate_upload(file: UploadFile) -> None:
    extension = (file.filename or "").rsplit(".", maxsplit=1)[-1].lower() if "." in (file.filename or "") else ""
    if extension in BLOCKED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Extensão de arquivo não permitida.")

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Tipo de arquivo não permitido.")

    current_pos = file.file.tell()
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(current_pos)

    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Arquivo excede o limite máximo de 5MB.")


@router.post("/storefront/upload")
def upload_storefront_file(
    file: UploadFile = File(...),
    tenant_id: str = Query(...),
    category: str = Query(...),
    subfolder: str | None = Query(default=None),
):
    try:
        _validate_upload(file)
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
        raise HTTPException(status_code=500, detail=f"Erro ao enviar arquivo para R2: {exc}") from exc
