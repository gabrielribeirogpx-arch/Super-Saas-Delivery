"""Explicit public SaaS enrollment. No operator secrets are exposed to browsers."""
from dataclasses import dataclass, field
import os
import re
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException, Request
from app.core.rate_limiter import InMemoryRateLimiterService

# A bounded, global per-process emergency brake; shared edge limits remain required.
_limiter = InMemoryRateLimiterService(limit=10, window_seconds=60)


def https_url(value):
    try:
        p = urlsplit(value)
        return bool(p.scheme == "https" and p.hostname and not p.username and not p.password and not p.fragment)
    except ValueError:
        return False


@dataclass(frozen=True)
class PublicSignupSettings:
    enabled: bool
    site_key: str
    secret: str = field(repr=False)
    origins: tuple[str, ...]
    terms_url: str
    privacy_url: str
    terms_version: str
    support_email: str

    @property
    def ready(self):
        return bool(self.enabled and self.site_key and self.secret and self.origins
            and all(https_url(o) and urlsplit(o).path == "" and not urlsplit(o).query for o in self.origins)
            and https_url(self.terms_url) and https_url(self.privacy_url)
            and re.fullmatch(r"[A-Za-z0-9._-]{1,64}", self.terms_version)
            and re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", self.support_email))


def public_signup_settings():
    return PublicSignupSettings(
        os.getenv("PUBLIC_SIGNUP_ENABLED", "false").lower() == "true",
        os.getenv("TURNSTILE_SITE_KEY", "").strip(), os.getenv("TURNSTILE_SECRET_KEY", "").strip(),
        tuple(o.strip().rstrip("/") for o in os.getenv("PUBLIC_SIGNUP_ORIGINS", "").split(",") if o.strip()),
        os.getenv("SALES_TERMS_URL", "").strip(), os.getenv("SALES_PRIVACY_URL", "").strip(),
        os.getenv("SALES_TERMS_VERSION", "").strip(), os.getenv("SALES_SUPPORT_EMAIL", "").strip(),
    )


def verify_public_signup(request: Request, payload, settings: PublicSignupSettings):
    if not settings.ready:
        raise HTTPException(503, "Cadastro público temporariamente indisponível")
    origin = request.headers.get("origin", "")
    if origin not in settings.origins:
        raise HTTPException(403, "Origem de cadastro não autorizada")
    if payload.custom_domain:
        raise HTTPException(400, "Configure seu domínio após contratar um plano compatível")
    if not payload.accept_terms or payload.terms_version != settings.terms_version:
        raise HTTPException(400, "Leia e aceite os termos atuais para continuar")
    if not payload.captcha_token:
        raise HTTPException(400, "Conclua a verificação de segurança")
    decision = _limiter.check(tenant_id="public-signup", endpoint="create")
    if not decision.allowed:
        raise HTTPException(429, "Muitas tentativas. Aguarde um minuto e tente novamente", headers={"Retry-After": str(decision.retry_after_seconds)})
    try:
        with httpx.Client(timeout=5, follow_redirects=False) as client:
            response = client.post("https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={"secret": settings.secret, "response": payload.captcha_token})
        if response.status_code != 200 or len(response.content) > 16384:
            raise ValueError()
        result = response.json()
        valid = (result.get("success") is True and result.get("hostname") == urlsplit(origin).hostname
            and result.get("action") == "signup")
    except (httpx.HTTPError, ValueError, AttributeError):
        raise HTTPException(503, "Verificação de segurança indisponível. Tente novamente") from None
    if not valid:
        raise HTTPException(400, "Verificação expirada ou inválida. Tente novamente")
