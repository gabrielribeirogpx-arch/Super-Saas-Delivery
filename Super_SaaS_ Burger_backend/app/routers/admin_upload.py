from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.tenant_public_settings import TenantPublicSettings
from app.routers.storefront_upload import _validate_upload
from app.services.r2_storage import upload_file

router = APIRouter(prefix="/api/admin", tags=["admin-upload"])
ADMIN_UPLOAD_ACCESS = require_role(["admin", "owner"])


class AdminLogoUploadResponse(BaseModel):
    logo_url: str


@router.post("/{tenant_id}/upload/logo", response_model=AdminLogoUploadResponse)
def upload_tenant_logo(
    tenant_id: int,
    file: UploadFile = File(...),
    _user: AdminUser = Depends(ADMIN_UPLOAD_ACCESS),
    db: Session = Depends(get_db),
):
    try:
        _validate_upload(file)
        logo_url = upload_file(
            file=file,
            tenant_id=str(tenant_id),
            category="branding",
            subfolder="logo",
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao enviar arquivo para R2: {exc}") from exc

    settings = (
        db.query(TenantPublicSettings)
        .filter(TenantPublicSettings.tenant_id == tenant_id)
        .first()
    )
    if not settings:
        settings = TenantPublicSettings(tenant_id=tenant_id)
        db.add(settings)

    settings.logo_url = logo_url
    db.commit()

    return AdminLogoUploadResponse(logo_url=logo_url)
