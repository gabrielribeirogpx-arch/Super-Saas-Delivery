from __future__ import annotations

import logging
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.core.domains import (
    get_platform_base_domains,
    is_reserved_platform_subdomain,
    normalize_domain,
)
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

        return cls._extract_platform_subdomain(normalized_host)

    @classmethod
    def resolve_tenant_from_request(cls, db: Session, request: Request) -> Tenant | None:
        """Resolve tenant deterministically using trusted priority.

        Priority:
        1) X-Tenant-Slug header (explicit tenant slug)
        2) X-Tenant-ID header (numeric tenant id or tenant slug, legacy)
        3) query tenant slug
        4) X-Forwarded-Host
        5) Host
        """

        requested_host = request.headers.get("host")
        forwarded_host = request.headers.get("x-forwarded-host")

        for header_name, strategy in (("x-tenant-slug", "x_tenant_slug"), ("x-tenant-id", "x_tenant_id")):
            header_tenant = (request.headers.get(header_name) or "").strip()
            if not header_tenant:
                continue
            tenant = cls._resolve_tenant_from_header(db, header_tenant)
            if tenant is not None:
                logger.info(
                    "event=tenant_resolved tenant_resolution_source=%s requested_host=%s requested_slug=%s resolved_tenant_id=%s",
                    strategy,
                    requested_host,
                    normalize_slug(header_tenant),
                    int(tenant.id),
                )
                return tenant
            logger.warning(
                "event=tenant_resolution_failed tenant_resolution_source=%s requested_host=%s requested_slug=%s resolved_tenant_id=None resolution_failed_reason=tenant_not_found_or_inactive",
                strategy,
                requested_host,
                normalize_slug(header_tenant),
            )

        query_tenant = (request.query_params.get("tenant") or "").strip().lower()
        if query_tenant:
            tenant = cls.find_active_tenant_by_slug(db, query_tenant)
            if tenant is not None:
                logger.info(
                    "event=tenant_resolved tenant_resolution_source=query_tenant requested_host=%s requested_slug=%s resolved_tenant_id=%s",
                    requested_host,
                    query_tenant,
                    int(tenant.id),
                )
                return tenant

        for strategy, host_header in (
            ("x_forwarded_host", request.headers.get("x-forwarded-host")),
            ("host", request.headers.get("host")),
        ):
            normalized_host = cls.normalize_host(host_header or "")
            if not normalized_host:
                continue
            if cls._is_platform_root_host(normalized_host) or cls._is_reserved_platform_host(normalized_host):
                continue
            tenant = cls.find_active_tenant_by_custom_domain(db, normalized_host)
            subdomain = None
            if tenant is None:
                subdomain = cls._extract_platform_subdomain(normalized_host)
                if not subdomain:
                    continue
                tenant = cls.find_active_tenant_by_slug(db, subdomain)
            if tenant is None:
                continue
            logger.info(
                "event=tenant_resolved tenant_resolution_source=%s requested_host=%s requested_slug=%s resolved_tenant_id=%s",
                strategy,
                host_header,
                subdomain,
                int(tenant.id),
            )
            return tenant

        logger.warning(
            "event=tenant_resolution_failed tenant_resolution_source=none requested_host=%s requested_slug=None resolved_tenant_id=None resolution_failed_reason=no_tenant_context x_forwarded_host=%s",
            requested_host,
            forwarded_host,
        )
        return None

    @classmethod
    def _resolve_tenant_from_header(cls, db: Session, header_tenant: str) -> Tenant | None:
        try:
            tenant_id = int(header_tenant)
        except (TypeError, ValueError):
            tenant_id = None

        if tenant_id is not None:
            return db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.is_active.is_(True)).first()

        tenant_slug = header_tenant.strip().lower()
        if not tenant_slug:
            return None
        return cls.find_active_tenant_by_slug(db, tenant_slug)

    @classmethod
    def _extract_subdomain_from_host_header(cls, host_header: str | None) -> str | None:
        normalized_host = cls.normalize_host(host_header or "")
        if not normalized_host:
            return None

        return cls._extract_platform_subdomain(normalized_host)

    @staticmethod
    def _get_base_domain() -> str:
        return get_platform_base_domains()[0]

    @classmethod
    def extract_subdomain(cls, host: str) -> str | None:
        normalized_host = cls.normalize_host(host)
        logger.info("Tenant resolution host: %s", normalized_host)
        if not normalized_host:
            raise TenantResolutionError("Invalid host")

        normalized_host = normalized_host.split(":")[0]
        subdomain = cls._extract_platform_subdomain(normalized_host)
        if not subdomain:
            raise TenantResolutionError("Invalid host")

        if not subdomain:
            raise TenantResolutionError("Subdomain is empty")

        return subdomain

    @classmethod
    def normalize_base_domain(cls, base_domain: str) -> str:
        return normalize_domain(base_domain)

    @classmethod
    def _extract_platform_subdomain(cls, normalized_host: str) -> str | None:
        for base_domain in get_platform_base_domains():
            subdomain = cls._extract_tenant_label(normalized_host, base_domain)
            if subdomain and not is_reserved_platform_subdomain(subdomain):
                return subdomain
        return None

    @classmethod
    def _is_reserved_platform_host(cls, normalized_host: str) -> bool:
        for base_domain in get_platform_base_domains():
            candidate = cls._extract_tenant_label_unchecked(normalized_host, base_domain)
            if candidate and is_reserved_platform_subdomain(candidate):
                return True
        return False

    @staticmethod
    def _is_platform_root_host(normalized_host: str) -> bool:
        return normalized_host in get_platform_base_domains()

    @staticmethod
    def _slug_lookup_candidates(slug: str) -> list[str]:
        exact_slug = (slug or "").strip().lower()
        if not exact_slug:
            return []

        candidates = [exact_slug]
        normalized_slug = normalize_slug(exact_slug)
        if normalized_slug and normalized_slug not in candidates:
            candidates.append(normalized_slug)
        return candidates

    @classmethod
    def find_active_tenant_by_slug(cls, db: Session, slug: str) -> Tenant | None:
        for candidate in cls._slug_lookup_candidates(slug):
            tenant = db.query(Tenant).filter(Tenant.slug == candidate, Tenant.is_active.is_(True)).first()
            if tenant is not None:
                return tenant
        return None

    @classmethod
    def find_active_tenant_by_custom_domain(cls, db: Session, host: str) -> Tenant | None:
        normalized_host = cls.normalize_host(host)
        if not normalized_host or "." not in normalized_host:
            return None
        return (
            db.query(Tenant)
            .filter(
                Tenant.custom_domain.ilike(normalized_host),
                Tenant.is_active.is_(True),
            )
            .first()
        )

    @classmethod
    def resolve_from_host(cls, db: Session, host: str) -> Tenant:
        normalized_host = cls.normalize_host(host)
        if cls._is_platform_root_host(normalized_host) or cls._is_reserved_platform_host(normalized_host):
            raise HTTPException(status_code=404, detail="Tenant not found")
        tenant = cls.find_active_tenant_by_custom_domain(db, normalized_host)
        if tenant is not None:
            return tenant
        try:
            subdomain = cls.extract_subdomain(normalized_host)
        except TenantResolutionError as exc:
            raise HTTPException(status_code=404, detail="Tenant not found") from exc
        if not subdomain:
            raise HTTPException(status_code=404, detail="Tenant not found")

        return cls.resolve_from_subdomain(db, subdomain)

    @staticmethod
    def resolve_from_subdomain(db: Session, subdomain: str) -> Tenant:
        requested_subdomain = (subdomain or "").strip().lower()
        if not normalize_slug(requested_subdomain):
            raise HTTPException(status_code=404, detail="Tenant not found")

        tenant = TenantResolver.find_active_tenant_by_slug(db, requested_subdomain)
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

        tenant_slug = normalize_slug(request.query_params.get("tenant") or "")
        if tenant_slug:
            tenant = getattr(request.state, "tenant", None)
            if tenant is not None and getattr(tenant, "slug", None) == tenant_slug:
                return getattr(tenant, "id", None)

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
        candidate = TenantResolver._extract_tenant_label_unchecked(normalized_host, base_domain)
        return None if is_reserved_platform_subdomain(candidate) else candidate

    @staticmethod
    def _extract_tenant_label_unchecked(normalized_host: str, base_domain: str) -> str | None:
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
