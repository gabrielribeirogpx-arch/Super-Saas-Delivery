from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from sqlalchemy.orm import Session

from app.models.admin_audit_log import AdminAuditLog


def log_admin_action(
    db: Session,
    *,
    tenant_id: int,
    user_id: int,
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    meta: Optional[Mapping[str, Any]] = None,
) -> AdminAuditLog:
    entry = AdminAuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        meta_json=json.dumps(meta) if meta else None,
    )
    db.add(entry)
    return entry
