from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from sqlalchemy.orm import Session

from app.models.admin_audit_log import AdminAuditLog


def log_admin_action(
    db: Session,
    *,
    tenant_id: int,
    user_id: int | None,
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    meta: Optional[Mapping[str, Any]] = None,
    actor_type: str = "user",
) -> AdminAuditLog:
    if actor_type not in {"user", "system", "provider"}:
        raise ValueError("Invalid audit actor type")
    if (actor_type == "user") != (user_id is not None):
        raise ValueError("Human actors require user_id; automatic actors must not have user_id")
    entry = AdminAuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        actor_type=actor_type,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        meta_json=json.dumps(meta) if meta else None,
    )
    db.add(entry)
    return entry
