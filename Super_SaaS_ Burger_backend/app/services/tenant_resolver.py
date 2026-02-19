from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import PUBLIC_BASE_DOMAIN
from app.models.tenant import Tenant


class TenantResolver:
    """Resolve tenant identity from host/path without coupling to authz/authn."""

    @staticmethod
    def normalize_host(host: str) -> str:
        normalized = (host or "").split(",")[0].strip().lower()
        if ":" in normalized:
            normalized = normalized.split(":")[0].strip()
        return normalized

    @classmethod
    def resolve_from_host(cls, db: Session, host: str) -> Tenant:
        normalized_host = cls.normalize_host(host)
        if not normalized_host:
            raise HTTPException(status_code=400, detail="Host ausente")

        if PUBLIC_BASE_DOMAIN and normalized_host.endswith(f".{PUBLIC_BASE_DOMAIN}"):
            subdomain = normalized_host.split(".")[0]
            print("Incoming subdomain:", subdomain)
            if not subdomain:
                raise HTTPException(status_code=404, detail="Tenant not found")
            tenant = db.query(Tenant).filter(Tenant.slug == subdomain).first()
            print("Tenant found:", tenant)
        else:
            tenant = (
                db.query(Tenant)
                .filter(func.lower(Tenant.custom_domain) == normalized_host)
                .first()
            )

        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return tenant

    @classmethod
    def resolve_tenant_id_from_request(cls, request: Request, tenant_id: int | None = None) -> int | None:
        if tenant_id is not None:
            return tenant_id

        path_tenant = request.path_params.get("tenant_id")
        if path_tenant is not None:
            try:
                return int(path_tenant)
            except (TypeError, ValueError):
                return None

        query_tenant = request.query_params.get("tenant_id")
        if query_tenant is not None:
            try:
                return int(query_tenant)
            except (TypeError, ValueError):
                return None

        return None
