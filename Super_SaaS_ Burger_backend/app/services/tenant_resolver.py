from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import PUBLIC_BASE_DOMAIN
from app.models.tenant import Tenant
from utils.slug import normalize_slug


class TenantResolver:
    """Resolve tenant identity from subdomain host only."""

    @staticmethod
    def normalize_host(host: str) -> str:
        normalized = (host or "").split(",")[0].strip().lower()
        if not normalized:
            return ""

        if "://" in normalized:
            normalized = urlsplit(normalized).hostname or ""
            return normalized.lower()

        normalized = normalized.split("/")[0].strip()
        if ":" in normalized:
            normalized = normalized.split(":")[0].strip()
        return normalized

    @classmethod
    def extract_subdomain_from_request(cls, request: Request) -> str | None:
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        return cls.extract_subdomain(host or "")

    @classmethod
    def extract_subdomain(cls, host: str) -> str | None:
        normalized_host = cls.normalize_host(host)
        if not normalized_host or not PUBLIC_BASE_DOMAIN:
            return None

        base_domain = PUBLIC_BASE_DOMAIN.strip().lower()
        if normalized_host == base_domain or not normalized_host.endswith(f".{base_domain}"):
            return None

        labels = normalized_host.split(".")
        base_labels = base_domain.split(".")
        sub_labels = labels[: len(labels) - len(base_labels)]
        if len(sub_labels) != 1:
            return None

        return normalize_slug(sub_labels[0]) or None

    @classmethod
    def resolve_from_host(cls, db: Session, host: str) -> Tenant:
        subdomain = cls.extract_subdomain(host)
        if not subdomain:
            raise HTTPException(status_code=404, detail="Tenant not found")

        return cls.resolve_from_subdomain(db, subdomain)

    @staticmethod
    def resolve_from_subdomain(db: Session, subdomain: str) -> Tenant:
        normalized_subdomain = normalize_slug(subdomain)
        if not normalized_subdomain:
            raise HTTPException(status_code=404, detail="Tenant not found")

        tenant = db.query(Tenant).filter(Tenant.slug == normalized_subdomain).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return tenant

    @classmethod
    def resolve_tenant_id_from_request(cls, request: Request, tenant_id: int | None = None) -> int | None:
        if tenant_id is not None:
            return tenant_id

        tenant_id_candidates = [
            request.path_params.get("tenant_id"),
            request.query_params.get("tenant_id"),
            request.headers.get("x-tenant-id"),
        ]
        for candidate in tenant_id_candidates:
            if candidate is None:
                continue
            try:
                return int(candidate)
            except (TypeError, ValueError):
                continue

        tenant = getattr(request.state, "tenant", None)
        if tenant is None:
            return None

        return getattr(tenant, "id", None)
