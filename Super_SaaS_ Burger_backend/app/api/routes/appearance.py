from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user
from app.schemas.appearance import AppearanceSettings
from app.services.appearance_service import appearance_service

router = APIRouter(prefix="/api", tags=["appearance"])


@router.get("/appearance", response_model=AppearanceSettings)
def get_appearance(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return appearance_service.get_appearance(db=db, tenant_id=current_user.tenant_id)


@router.put("/appearance", response_model=AppearanceSettings)
def update_appearance(
    payload: AppearanceSettings,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return appearance_service.update_appearance(
        db=db,
        tenant_id=current_user.tenant_id,
        data=payload,
    )
