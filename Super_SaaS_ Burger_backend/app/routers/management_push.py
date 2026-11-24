from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_admin_user
from app.models.admin_user import AdminUser
from app.models.management_push import ManagementPushDevice
from app.services.management_push import ROLES, enabled

router = APIRouter(prefix="/api/admin/management-push", tags=["management push"])


class DeviceRegistration(BaseModel):
    token: str = Field(min_length=16, max_length=512, pattern=r"^[A-Za-z0-9_:-]+$")
    binding: UUID


@router.put("/device", status_code=204)
def subscribe(data: DeviceRegistration, user: AdminUser = Depends(require_admin_user),
              db: Session = Depends(get_db)):
    if not enabled():
        raise HTTPException(503, "Notificações indisponíveis")
    if (user.role not in ROLES or user.tenant_id <= 0 or
            (user.email_verification_required and not user.email_verified_at)):
        raise HTTPException(403, "Acesso negado")
    values = dict(tenant_id=user.tenant_id, admin_user_id=user.id,
                  credential_version=user.credential_version, binding=str(data.binding),
                  expires_at=datetime.now(timezone.utc) + timedelta(days=30))
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    db.execute(insert(ManagementPushDevice).values(token=data.token, **values).on_conflict_do_update(
        index_elements=[ManagementPushDevice.token], set_=values,
    ))
    db.commit()
    return Response(status_code=204)


@router.delete("/device", status_code=204)
def unsubscribe(data: DeviceRegistration, user: AdminUser = Depends(require_admin_user),
                db: Session = Depends(get_db)):
    db.query(ManagementPushDevice).filter_by(token=data.token, binding=str(data.binding),
        tenant_id=user.tenant_id, admin_user_id=user.id).delete()
    db.commit()
    return Response(status_code=204)
