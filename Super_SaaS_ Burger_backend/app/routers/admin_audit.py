from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_audit_log import AdminAuditLog
from app.models.admin_user import AdminUser

router = APIRouter(prefix="/api/admin/audit", tags=["admin-audit"])


class AdminAuditRead(BaseModel):
    id: int
    tenant_id: int
    user_id: int
    user_name: Optional[str]
    user_email: Optional[str]
    action: str
    entity_type: Optional[str]
    entity_id: Optional[int]
    meta: Optional[Dict[str, Any]]
    created_at: datetime


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(cleaned)
        return parsed.replace(tzinfo=None)
    except ValueError:
        return None


@router.get("", response_model=List[AdminAuditRead])
def list_audit_logs(
    tenant_id: Optional[int] = None,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    limit: int = Query(200, ge=1, le=500),
    user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    resolved_tenant_id = tenant_id if tenant_id is not None else int(user.tenant_id)

    if int(user.tenant_id) != int(resolved_tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant não autorizado")

    start_dt = _parse_datetime(from_date)
    end_dt = _parse_datetime(to_date)

    query = (
        db.query(AdminAuditLog, AdminUser)
        .outerjoin(AdminUser, AdminUser.id == AdminAuditLog.user_id)
        .filter(AdminAuditLog.tenant_id == resolved_tenant_id)
    )

    if start_dt:
        query = query.filter(AdminAuditLog.created_at >= start_dt)
    if end_dt:
        query = query.filter(AdminAuditLog.created_at <= end_dt)
    if user_id:
        query = query.filter(AdminAuditLog.user_id == user_id)
    if action:
        query = query.filter(AdminAuditLog.action == action)

    rows = (
        query.order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc())
        .limit(limit)
        .all()
    )

    results: List[Dict[str, Any]] = []
    for entry, admin_user in rows:
        meta = None
        if entry.meta_json:
            try:
                meta = json.loads(entry.meta_json)
            except json.JSONDecodeError:
                meta = {"raw": entry.meta_json}
        results.append(
            {
                "id": entry.id,
                "tenant_id": entry.tenant_id,
                "user_id": entry.user_id,
                "user_name": admin_user.name if admin_user else None,
                "user_email": admin_user.email if admin_user else None,
                "action": entry.action,
                "entity_type": entry.entity_type,
                "entity_id": entry.entity_id,
                "meta": meta,
                "created_at": entry.created_at,
            }
        )

    return results
