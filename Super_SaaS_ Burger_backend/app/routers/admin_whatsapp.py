from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.whatsapp_config import WhatsAppConfig
from app.models.whatsapp_message_log import WhatsAppMessageLog
from app.services.admin_audit import log_admin_action
from app.whatsapp.service import WhatsAppService

router = APIRouter(prefix="/api/admin", tags=["admin-whatsapp"])


class WhatsAppConfigRead(BaseModel):
    id: int
    tenant_id: int
    provider: str
    phone_number_id: Optional[str] = None
    waba_id: Optional[str] = None
    access_token_masked: Optional[str] = None
    verify_token: Optional[str] = None
    webhook_secret: Optional[str] = None
    is_enabled: bool


class WhatsAppConfigUpdate(BaseModel):
    provider: str = Field(..., min_length=1)
    phone_number_id: Optional[str] = None
    waba_id: Optional[str] = None
    access_token: Optional[str] = None
    verify_token: Optional[str] = None
    webhook_secret: Optional[str] = None
    is_enabled: bool = False
    update_token: bool = False


class WhatsAppTestMessage(BaseModel):
    phone: str = Field(..., min_length=8)
    message: str = Field(..., min_length=1)


def _mask_token(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 4:
        return "****"
    return f"****{value[-4:]}"


def _ensure_tenant(user: AdminUser, tenant_id: int) -> None:
    if int(user.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant não autorizado")


def _serialize_config(config: WhatsAppConfig) -> dict:
    return {
        "id": config.id,
        "tenant_id": config.tenant_id,
        "provider": config.provider,
        "phone_number_id": config.phone_number_id,
        "waba_id": config.waba_id,
        "access_token_masked": _mask_token(config.access_token),
        "verify_token": config.verify_token,
        "webhook_secret": config.webhook_secret,
        "is_enabled": config.is_enabled,
    }


@router.get("/{tenant_id}/whatsapp/config", response_model=WhatsAppConfigRead)
def get_whatsapp_config(
    tenant_id: int,
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    _ensure_tenant(user, tenant_id)
    config = db.query(WhatsAppConfig).filter(WhatsAppConfig.tenant_id == tenant_id).first()
    if not config:
        config = WhatsAppConfig(tenant_id=tenant_id, provider="mock", is_enabled=False)
        db.add(config)
        db.commit()
        db.refresh(config)
    return _serialize_config(config)


@router.put("/{tenant_id}/whatsapp/config", response_model=WhatsAppConfigRead)
def update_whatsapp_config(
    tenant_id: int,
    payload: WhatsAppConfigUpdate,
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    _ensure_tenant(user, tenant_id)

    provider = payload.provider.strip().lower()
    if provider not in {"mock", "cloud"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider inválido")

    config = db.query(WhatsAppConfig).filter(WhatsAppConfig.tenant_id == tenant_id).first()
    if not config:
        config = WhatsAppConfig(tenant_id=tenant_id)
        db.add(config)

    config.provider = provider
    config.phone_number_id = payload.phone_number_id.strip() if payload.phone_number_id else None
    config.waba_id = payload.waba_id.strip() if payload.waba_id else None
    config.verify_token = payload.verify_token.strip() if payload.verify_token else None
    config.webhook_secret = payload.webhook_secret.strip() if payload.webhook_secret else None
    config.is_enabled = bool(payload.is_enabled)

    if payload.update_token:
        config.access_token = payload.access_token.strip() if payload.access_token else None

    log_admin_action(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action="whatsapp.config.updated",
        entity_type="whatsapp_config",
        entity_id=config.id,
        meta={"provider": config.provider, "is_enabled": config.is_enabled},
    )

    db.commit()
    db.refresh(config)
    return _serialize_config(config)


@router.post("/{tenant_id}/whatsapp/test-message")
def send_whatsapp_test_message(
    tenant_id: int,
    payload: WhatsAppTestMessage,
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    _ensure_tenant(user, tenant_id)
    service = WhatsAppService()
    log_entry = service.send_text(
        db,
        tenant_id=tenant_id,
        to_phone=payload.phone,
        text=payload.message,
        context={"source": "admin_test"},
    )

    log_admin_action(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action="whatsapp.test_message",
        entity_type="whatsapp_message_log",
        entity_id=log_entry.id if log_entry else None,
        meta={"phone": payload.phone, "status": log_entry.status if log_entry else "skipped"},
    )
    db.commit()

    return {
        "id": log_entry.id,
        "status": log_entry.status,
        "error": log_entry.error,
    }


@router.get("/{tenant_id}/whatsapp/logs", response_model=List[dict])
def list_whatsapp_logs(
    tenant_id: int,
    phone: Optional[str] = None,
    status: Optional[str] = None,
    direction: Optional[str] = None,
    from_phone: Optional[str] = None,
    to_phone: Optional[str] = None,
    limit: int = 50,
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    _ensure_tenant(user, tenant_id)

    query = db.query(WhatsAppMessageLog).filter(WhatsAppMessageLog.tenant_id == tenant_id)
    if phone:
        query = query.filter(
            (WhatsAppMessageLog.to_phone == phone) | (WhatsAppMessageLog.from_phone == phone)
        )
    if status:
        query = query.filter(WhatsAppMessageLog.status == status)
    if direction:
        query = query.filter(WhatsAppMessageLog.direction == direction)
    if from_phone:
        query = query.filter(WhatsAppMessageLog.from_phone == from_phone)
    if to_phone:
        query = query.filter(WhatsAppMessageLog.to_phone == to_phone)

    logs = (
        query.order_by(WhatsAppMessageLog.created_at.desc())
        .limit(min(max(limit, 1), 200))
        .all()
    )

    return [
        {
            "id": entry.id,
            "tenant_id": entry.tenant_id,
            "direction": entry.direction,
            "to_phone": entry.to_phone,
            "from_phone": entry.from_phone,
            "template_name": entry.template_name,
            "message_type": entry.message_type,
            "status": entry.status,
            "error": entry.error,
            "provider_message_id": entry.provider_message_id,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
        for entry in logs
    ]
