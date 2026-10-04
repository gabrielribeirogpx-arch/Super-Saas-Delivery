from __future__ import annotations

import os
from urllib.parse import urlsplit


DEFAULT_PLATFORM_BASE_DOMAINS = (
    "servicedelivery.com.br",
    "fomizero.com.br",
)

RESERVED_PLATFORM_SUBDOMAINS = frozenset(
    {
        "www",
        "app",
        "api",
        "admin",
        "mail",
        "status",
        "support",
        "help",
        "docs",
        "cdn",
        "assets",
        "static",
        "auth",
        "billing",
        "webhook",
        "m",
    }
)


def normalize_domain(value: str | None) -> str:
    raw = (value or "").split(",", 1)[0].strip().strip("\"'").lower()
    if not raw:
        return ""

    if "://" in raw:
        raw = urlsplit(raw).hostname or ""
    else:
        raw = raw.split("/", 1)[0]
        if raw.count(":") == 1:
            raw = raw.split(":", 1)[0]

    if raw.startswith("*."):
        raw = raw[2:]
    return raw.strip().strip(".")


def get_platform_base_domains() -> tuple[str, ...]:
    """Return canonical platform bases plus legacy configuration, deduplicated.

    PLATFORM_BASE_DOMAINS is the canonical multi-value setting. BASE_DOMAIN and
    PUBLIC_BASE_DOMAIN remain accepted so existing installations keep working.
    """

    configured = os.getenv("PLATFORM_BASE_DOMAINS", "")
    candidates = configured.split(",") if configured else list(DEFAULT_PLATFORM_BASE_DOMAINS)
    candidates.extend(
        [
            os.getenv("BASE_DOMAIN", ""),
            os.getenv("PUBLIC_BASE_DOMAIN", ""),
        ]
    )

    domains: list[str] = []
    for candidate in candidates:
        normalized = normalize_domain(candidate)
        if normalized and normalized not in domains:
            domains.append(normalized)
    return tuple(domains or DEFAULT_PLATFORM_BASE_DOMAINS)


def is_reserved_platform_subdomain(slug: str | None) -> bool:
    return (slug or "").strip().lower() in RESERVED_PLATFORM_SUBDOMAINS
