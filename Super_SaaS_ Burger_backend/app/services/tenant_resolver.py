from __future__ import annotations

import logging
import os
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import PUBLIC_BASE_DOMAIN
from app.models.tenant import Tenant
from app.services.auth import decode_access_token
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
        host = request.headers.get("host")
        logger.info(
            "event=tenant_resolution_headers host=%s x_forwarded_host=%s x_tenant_id=%s",
            host,
            forwarded_host,
            request.headers.get("x-tenant-id"),
        )

        host = forwarded_host or host or ""
        normalized_host = cls.normalize_host(host)
        if not normalized_host:
            return None

        base_domain = cls.normalize_base_domain(
            os.getenv("BASE_DOMAIN", "servicedelivery.com.br")
        )
        if not base_domain:
            return None

        subdomain = cls._extract_tenant_label(normalized_host, base_domain)

        if not subdomain:
            return None

        normalized_subdomain = normalize_slug(subdomain)
        return normalized_subdomain or None

    @classmethod
    def resolve_tenant_from_request(cls, db: Session, request: Request) -> Tenant | None:
        """Resolve tenant deterministically using trusted priority.

        Priority:
        1) X-Tenant-ID header (numeric tenant id or tenant slug)
        2) X-Forwarded-Host
        3) Host
        """

        header_tenant = (request.headers.get("x-tenant-id") or "").strip()
        if header_tenant:
            tenant = cls._resolve_tenant_from_header(db, header_tenant)
            if tenant is not None:
                logger.info(
                    "event=tenant_resolved strategy=x_tenant_id tenant_id=%s header_value=%s",
                    int(tenant.id),
                    header_tenant,
                )
                return tenant

        for strategy, host_header in (
            ("x_forwarded_host", request.headers.get("x-forwarded-host")),
            ("host", request.headers.get("host")),
        ):
            subdomain = cls._extract_subdomain_from_host_header(host_header)
            if not subdomain:
                continue
            try:
                tenant = cls.resolve_from_subdomain(db, subdomain)
            except HTTPException:
                continue
            logger.info(
                "event=tenant_resolved strategy=%s tenant_id=%s subdomain=%s",
                strategy,
                int(tenant.id),
                subdomain,
            )
            return tenant

        logger.warning(
            "event=tenant_resolution_failed host=%s x_forwarded_host=%s x_tenant_id=%s",
            request.headers.get("host"),
            request.headers.get("x-forwarded-host"),
            request.headers.get("x-tenant-id"),
        )
        return None

    @classmethod
    def _resolve_tenant_from_header(cls, db: Session, header_tenant: str) -> Tenant | None:
        try:
            tenant_id = int(header_tenant)
        except (TypeError, ValueError):
            tenant_id = None

        if tenant_id is not None:
            return db.query(Tenant).filter(Tenant.id == tenant_id).first()

        tenant_slug = normalize_slug(header_tenant)
        if not tenant_slug:
            return None
        return db.query(Tenant).filter(Tenant.slug == tenant_slug).first()

    @classmethod
    def _extract_subdomain_from_host_header(cls, host_header: str | None) -> str | None:
        normalized_host = cls.normalize_host(host_header or "")
        if not normalized_host:
            return None

        base_domain = cls.normalize_base_domain(
            os.getenv("BASE_DOMAIN") or os.getenv("PUBLIC_BASE_DOMAIN") or PUBLIC_BASE_DOMAIN or "servicedelivery.com.br"
        )
        if not base_domain:
            return None

        subdomain = cls._extract_tenant_label(normalized_host, base_domain)
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

        subdomain = cls._extract_tenant_label(normalized_host, base_domain)
        if not subdomain:
            raise TenantResolutionError("Invalid host")

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

        authenticated_tenant_id = cls._extract_authenticated_tenant_id(request)
        if authenticated_tenant_id is not None:
            return authenticated_tenant_id

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
    @staticmethod
    def _extract_authenticated_tenant_id(request: Request) -> int | None:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            if token:
                try:
                    payload = decode_access_token(token)
                except Exception:
                    return None
                tenant_id = payload.get("tenant_id")
                if tenant_id is None:
                    return None
                try:
                    return int(tenant_id)
                except (TypeError, ValueError):
                    return None
        return None
    @staticmethod
    def _extract_tenant_label(normalized_host: str, base_domain: str) -> str | None:
        if not normalized_host or not base_domain:
            return None

        if normalized_host == base_domain:
            return None

        suffix = f".{base_domain}"
        if not normalized_host.endswith(suffix):
            return None

        prefix = normalized_host[: -len(suffix)]
        if not prefix:
            return None

        labels = [label for label in prefix.split(".") if label]
        if not labels:
            return None

        return labels[-1]
