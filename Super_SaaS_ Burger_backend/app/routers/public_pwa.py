from __future__ import annotations

import hashlib
import io
import re
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.tenant import Tenant
from app.models.tenant_public_settings import TenantPublicSettings
from app.services.tenant_resolver import TenantResolver

router = APIRouter(prefix="/api/public/pwa", tags=["public-pwa"])
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_ICON_CACHE: dict[str, bytes] = {}
_MAX_LOGO_BYTES = 4 * 1024 * 1024
_ALLOWED_LOGO_SCHEMES = {"http", "https"}
_ALLOWED_ICON_SIZES = {180, 192, 512}


def _resolve_tenant(request: Request, db: Session) -> Tenant:
    tenant = TenantResolver.resolve_tenant_from_request(db, request)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found for host")
    return tenant


def _settings(db: Session, tenant_id: int) -> TenantPublicSettings | None:
    return db.query(TenantPublicSettings).filter(TenantPublicSettings.tenant_id == tenant_id).first()


def _color(value: str | None, fallback: str = "#ffffff") -> str:
    value = (value or "").strip()
    return value if _HEX.match(value) else fallback


def _store_name(tenant: Tenant) -> str:
    return (getattr(tenant, "business_name", None) or getattr(tenant, "name", None) or getattr(tenant, "slug", None) or "Loja").strip()


def _version(tenant: Tenant, settings: TenantPublicSettings | None) -> str:
    raw = "|".join([
        str(getattr(tenant, "slug", "")),
        str(getattr(tenant, "business_name", "")),
        str(getattr(settings, "logo_url", "") if settings else ""),
        str(getattr(settings, "primary_color", "") if settings else ""),
        str(getattr(settings, "updated_at", "") if settings else ""),
    ])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _headers(max_age: int = 300) -> dict[str, str]:
    return {"Cache-Control": f"public, max-age={max_age}, must-revalidate", "Vary": "Host, X-Forwarded-Host"}


@router.get("/manifest")
def manifest(request: Request, db: Session = Depends(get_db)):
    tenant = _resolve_tenant(request, db)
    settings = _settings(db, int(tenant.id))
    name = _store_name(tenant)
    primary = _color(getattr(settings, "primary_color", None), "#111827")
    version = _version(tenant, settings)
    payload = {
        "name": name,
        "short_name": name[:12].strip() or "Loja",
        "description": f"Cardápio digital de {name}",
        "id": f"/?tenant={tenant.slug}",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "theme_color": primary,
        "background_color": "#ffffff",
        "lang": "pt-BR",
        "icons": [
            {"src": f"/api/public/pwa/icon/180?v={version}", "sizes": "180x180", "type": "image/png", "purpose": "any"},
            {"src": f"/api/public/pwa/icon/192?v={version}", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": f"/api/public/pwa/icon/512?v={version}", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": f"/api/public/pwa/icon/512?purpose=maskable&v={version}", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    return JSONResponse(payload, media_type="application/manifest+json", headers=_headers())


def _load_logo(url: str | None) -> Image.Image | None:
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_LOGO_SCHEMES or not parsed.netloc:
        return None
    try:
        with httpx.Client(timeout=4, follow_redirects=True) as client:
            response = client.get(url, headers={"Accept": "image/png,image/jpeg,image/webp"})
            ctype = response.headers.get("content-type", "").lower()
            if response.status_code != 200 or not ctype.startswith("image/") or "svg" in ctype:
                return None
            content = response.content[: _MAX_LOGO_BYTES + 1]
            if len(content) > _MAX_LOGO_BYTES:
                return None
        image = Image.open(io.BytesIO(content))
        image.load()
        if image.width > 4096 or image.height > 4096:
            return None
        return ImageOps.exif_transpose(image).convert("RGBA")
    except (httpx.HTTPError, OSError, UnidentifiedImageError):
        return None


def _png_icon(tenant: Tenant, settings: TenantPublicSettings | None, size: int, maskable: bool) -> bytes:
    bg = _color(getattr(settings, "primary_color", None), "#111827")
    canvas = Image.new("RGBA", (size, size), bg)
    safe_ratio = 0.60 if maskable else 0.74
    max_logo = int(size * safe_ratio)
    logo = _load_logo(getattr(settings, "logo_url", None) if settings else None)
    if logo:
        logo.thumbnail((max_logo, max_logo), Image.Resampling.LANCZOS)
        x = (size - logo.width) // 2
        y = (size - logo.height) // 2
        canvas.alpha_composite(logo, (x, y))
    else:
        draw = ImageDraw.Draw(canvas)
        initial = (_store_name(tenant).strip()[:1] or "L").upper()
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(size * 0.42))
        except OSError:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), initial, font=font)
        draw.text(((size - (bbox[2] - bbox[0])) / 2, (size - (bbox[3] - bbox[1])) / 2 - size * 0.04), initial, fill="#ffffff", font=font)
    out = io.BytesIO()
    canvas.convert("RGBA").save(out, format="PNG", optimize=True)
    return out.getvalue()


@router.get("/icon/{size}")
def icon(size: int, request: Request, purpose: str | None = Query(default=None), db: Session = Depends(get_db)):
    if size not in _ALLOWED_ICON_SIZES:
        raise HTTPException(status_code=404, detail="Unsupported icon size")
    tenant = _resolve_tenant(request, db)
    settings = _settings(db, int(tenant.id))
    maskable = purpose == "maskable"
    cache_key = f"{tenant.slug}:{_version(tenant, settings)}:{size}:{'maskable' if maskable else 'any'}"
    png = _ICON_CACHE.get(cache_key)
    if png is None:
        png = _png_icon(tenant, settings, size, maskable)
        _ICON_CACHE[cache_key] = png
    return Response(content=png, media_type="image/png", headers=_headers(86400))
