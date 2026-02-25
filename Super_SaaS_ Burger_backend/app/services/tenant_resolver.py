from __future__ import annotations

import logging
import os
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import PUBLIC_BASE_DOMAIN
from app.models.tenant import Tenant
from utils.slug import normalize_slug


logger = logging.getLogger(__name__)


class TenantResolutionError(Exception):
    pass


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
        forwarded_host = request.headers.get("x-forwarded-host")
        logger.warning(f"Tenant resolution → forwarded_host={forwarded_host}")

        host = forwarded_host or request.headers.get("host") or ""
        normalized_host = cls.normalize_host(host)
        if not normalized_host:
            return None

        base_domain = cls.normalize_base_domain(
            os.getenv("BASE_DOMAIN", "servicedelivery.com.br")
        )
        if not base_domain:
            return None

        subdomain: str | None
        if normalized_host.endswith(base_domain):
            subdomain = normalized_host.replace(f".{base_domain}", "", 1)
        else:
            subdomain = None

        if not subdomain:
            return None

        normalized_subdomain = normalize_slug(subdomain)
        return normalized_subdomain or None

    @staticmethod
    def _get_base_domain() -> str:
        base_domain = os.getenv("BASE_DOMAIN") or os.getenv("PUBLIC_BASE_DOMAIN") or PUBLIC_BASE_DOMAIN or "servicedelivery.com.br"
        return TenantResolver.normalize_base_domain(base_domain)

    @classmethod
    def extract_subdomain(cls, host: str) -> str | None:
        normalized_host = cls.normalize_host(host)
        logger.info("Tenant resolution host: %s", normalized_host)
        if not normalized_host:
            raise TenantResolutionError("Invalid host")

        normalized_host = normalized_host.split(":")[0]
        base_domain = cls._get_base_domain()
        if not base_domain:
            raise TenantResolutionError("Invalid host")

        if normalized_host == base_domain:
            raise TenantResolutionError("Subdomain is empty")

        if not normalized_host.endswith(base_domain):
            raise TenantResolutionError("Invalid host")

        subdomain = normalized_host.replace(f".{base_domain}", "", 1)
        if not subdomain:
            raise TenantResolutionError("Subdomain is empty")

        normalized_subdomain = normalize_slug(subdomain)
        if not normalized_subdomain:
            raise TenantResolutionError("Subdomain is empty")

        return normalized_subdomain

    @classmethod
    def normalize_base_domain(cls, base_domain: str) -> str:
        normalized = cls.normalize_host(base_domain or "")
        if normalized.startswith("*."):
            normalized = normalized[2:]
        return normalized.lstrip(".")

    @classmethod
    def resolve_from_host(cls, db: Session, host: str) -> Tenant:
        try:
            subdomain = cls.extract_subdomain(host)
        except TenantResolutionError as exc:
            raise HTTPException(status_code=404, detail="Tenant not found") from exc
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
