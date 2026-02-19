from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.metrics import request_metrics
from app.deps import require_role
from app.models.admin_user import AdminUser

router = APIRouter(prefix="/internal/metrics", tags=["internal-metrics"])


@router.get("/tenants")
def tenant_metrics(_user: AdminUser = Depends(require_role(["admin"]))):
    return {"tenants": request_metrics.snapshot_per_tenant()}
