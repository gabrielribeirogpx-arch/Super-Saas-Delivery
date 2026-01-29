from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.ai_config import AIConfig
from app.models.ai_message_log import AIMessageLog
from app.services.admin_audit import log_admin_action

router = APIRouter(prefix="/api/admin", tags=["admin-ai"])


class AIConfigRead(BaseModel):
    id: int
    tenant_id: int
    provider: str
    enabled: bool
    model: Optional[str] = None
    temperature: Optional[float] = None
    system_prompt: Optional[str] = None


class AIConfigUpdate(BaseModel):
    provider: str = Field(..., min_length=1)
    enabled: bool = False
    model: Optional[str] = None
    temperature: Optional[float] = None
    system_prompt: Optional[str] = None


def _ensure_tenant(user: AdminUser, tenant_id: int) -> None:
    if int(user.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant não autorizado")


def _serialize_config(config: AIConfig) -> dict:
    return {
        "id": config.id,
        "tenant_id": config.tenant_id,
        "provider": config.provider,
        "enabled": config.enabled,
        "model": config.model,
        "temperature": config.temperature,
        "system_prompt": config.system_prompt,
    }


@router.get("/{tenant_id}/ai/config", response_model=AIConfigRead)
def get_ai_config(
    tenant_id: int,
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    _ensure_tenant(user, tenant_id)
    config = db.query(AIConfig).filter(AIConfig.tenant_id == tenant_id).first()
    if not config:
        config = AIConfig(tenant_id=tenant_id, provider="mock", enabled=False)
        db.add(config)
        db.commit()
        db.refresh(config)
    return _serialize_config(config)


@router.put("/{tenant_id}/ai/config", response_model=AIConfigRead)
def update_ai_config(
    tenant_id: int,
    payload: AIConfigUpdate,
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    _ensure_tenant(user, tenant_id)

    provider = payload.provider.strip().lower()
    if provider not in {"mock", "gemini"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider inválido")

    config = db.query(AIConfig).filter(AIConfig.tenant_id == tenant_id).first()
    if not config:
        config = AIConfig(tenant_id=tenant_id)
        db.add(config)

    config.provider = provider
    config.enabled = bool(payload.enabled)
    config.model = payload.model.strip() if payload.model else None
    config.temperature = payload.temperature
    config.system_prompt = payload.system_prompt.strip() if payload.system_prompt else None

    log_admin_action(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action="ai.config.updated",
        entity_type="ai_config",
        entity_id=config.id,
        meta={"provider": config.provider, "enabled": config.enabled},
    )

    db.commit()
    db.refresh(config)
    return _serialize_config(config)


@router.get("/{tenant_id}/ai/logs", response_model=List[dict])
def list_ai_logs(
    tenant_id: int,
    phone: Optional[str] = None,
    direction: Optional[str] = None,
    limit: int = 100,
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    _ensure_tenant(user, tenant_id)

    query = db.query(AIMessageLog).filter(AIMessageLog.tenant_id == tenant_id)
    if phone:
        query = query.filter(AIMessageLog.phone == phone)
    if direction:
        query = query.filter(AIMessageLog.direction == direction)

    logs = query.order_by(AIMessageLog.created_at.desc()).limit(min(max(limit, 1), 200)).all()

    return [
        {
            "id": entry.id,
            "tenant_id": entry.tenant_id,
            "phone": entry.phone,
            "direction": entry.direction,
            "provider": entry.provider,
            "error": entry.error,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
        for entry in logs
    ]
