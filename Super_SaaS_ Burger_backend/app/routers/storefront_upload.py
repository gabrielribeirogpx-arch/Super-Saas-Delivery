from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.services.r2_storage import upload_file

router = APIRouter()


@router.post("/storefront/upload")
def upload_storefront_file(
    file: UploadFile = File(...),
    tenant_id: str = Query(...),
):
    try:
        file_url = upload_file(file=file, tenant_id=tenant_id)
        return {"url": file_url}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao enviar arquivo para R2: {exc}") from exc
