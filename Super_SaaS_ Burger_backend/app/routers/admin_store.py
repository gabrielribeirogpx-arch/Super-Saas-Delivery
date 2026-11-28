from __future__ import annotations

import os
from datetime import datetime, timezone
from urllib.parse import urlencode
from uuid import UUID

import httpx
from cryptography.fernet import InvalidToken

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.ifood_connection import IFoodConnection
from app.models.ifood_event import IFoodEvent
from app.models.tenant import Tenant
from app.services.ifood_connections import OAUTH_URL, exchange_tokens, production_oauth, seal, unseal
from app.services.ifood_events import IFOOD_API

router = APIRouter(prefix="/api/admin/store", tags=["admin-store"])


class AdminStoreStatusPatch(BaseModel):
    manual_open_status: bool


class AdminStoreResponse(BaseModel):
    id: int
    slug: str
    custom_domain: str | None
    business_name: str
    manual_open_status: bool
    estimated_prep_time: str | None
    delivery_fee: float


class AdminStorePatch(BaseModel):
    manual_open_status: bool | None = None
    estimated_prep_time: str | None = Field(default=None, max_length=50)
    delivery_fee: float | None = Field(default=None, ge=0)


def _serialize_tenant(tenant: Tenant) -> AdminStoreResponse:
    return AdminStoreResponse(
        id=tenant.id,
        slug=tenant.slug,
        custom_domain=tenant.custom_domain,
        business_name=tenant.business_name,
        manual_open_status=tenant.manual_open_status,
        estimated_prep_time=tenant.estimated_prep_time,
        delivery_fee=float(tenant.delivery_fee or 0),
    )


@router.get("", response_model=AdminStoreResponse)
def get_store(
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado")
    return _serialize_tenant(tenant)


@router.patch("", response_model=AdminStoreResponse)
def update_store(
    payload: AdminStorePatch,
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado")

    if payload.manual_open_status is not None:
        tenant.manual_open_status = payload.manual_open_status

    if payload.estimated_prep_time is not None:
        normalized_prep_time = payload.estimated_prep_time.strip()
        tenant.estimated_prep_time = normalized_prep_time or None

    if payload.delivery_fee is not None:
        tenant.delivery_fee = payload.delivery_fee

    db.commit()
    db.refresh(tenant)

    return _serialize_tenant(tenant)


@router.patch("/status", response_model=AdminStoreResponse)
def update_store_status(
    payload: AdminStoreStatusPatch,
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado")

    tenant.manual_open_status = payload.manual_open_status
    db.commit()
    db.refresh(tenant)

    return _serialize_tenant(tenant)


class IFoodEventSummary(BaseModel):
    code: str
    received_at: datetime


class IFoodIntegrationStatus(BaseModel):
    last_event: IFoodEventSummary | None
    production_available: bool = False
    merchant_id: str | None = None
    merchant_name: str | None = None


@router.get("/integrations/ifood", response_model=IFoodIntegrationStatus, response_model_exclude_unset=True)
def get_ifood_integration(
    response: Response,
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    oauth = production_oauth(user.tenant_id)
    integration = IFoodIntegrationStatus(last_event=None)
    if oauth:
        integration.production_available = True
        connection = db.get(IFoodConnection, user.tenant_id)
        if connection:
            integration.merchant_id = connection.merchant_id
            integration.merchant_name = connection.merchant_name
    event = (
        db.query(IFoodEvent.code, IFoodEvent.received_at)
        .filter(IFoodEvent.tenant_id == user.tenant_id)
        .order_by(IFoodEvent.received_at.desc(), IFoodEvent.event_id.desc())
        .first()
    )
    if event is None:
        return integration

    # SQLite returns timestamps without an offset, including UTC server defaults.
    received_at = event.received_at
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    integration.last_event = IFoodEventSummary(code=event.code, received_at=received_at)
    return integration


class IFoodConnectRequest(BaseModel):
    challenge: str = Field(min_length=1, max_length=8192)
    authorization_code: str = Field(min_length=1, max_length=128)
    merchant_id: UUID


@router.post("/integrations/ifood/authorize")
def start_ifood_authorization(
    response: Response,
    user: AdminUser = Depends(require_role(["owner"])),
):
    response.headers["Cache-Control"] = "no-store"
    oauth = production_oauth(user.tenant_id)
    if oauth is None:
        raise HTTPException(404, "Conexão com o iFood indisponível para esta loja.")
    try:
        with httpx.Client(timeout=8) as client:
            remote = client.post(f"{OAUTH_URL}/userCode", data={"clientId": oauth.client_id})
            remote.raise_for_status()
            payload = remote.json()
        verifier = payload["authorizationCodeVerifier"]
        code = payload["userCode"]
        ttl = min(int(payload["expiresIn"]), 600)
        if not isinstance(verifier, str) or not verifier or not isinstance(code, str) or not code or ttl <= 0:
            raise ValueError("Invalid iFood challenge")
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        raise HTTPException(502, "Não foi possível iniciar a autorização no iFood.") from None
    return {
        "url": f"https://portal.ifood.com.br/apps/code?{urlencode({'c': code})}",
        "challenge": seal(oauth, {
            "purpose": "authorize", "tenant": user.tenant_id, "user": user.id,
            "client": oauth.client_id, "verifier": verifier,
            "expires": int(datetime.now(timezone.utc).timestamp()) + ttl,
        }),
    }


@router.post("/integrations/ifood/connect")
def connect_ifood(
    payload: IFoodConnectRequest,
    response: Response,
    user: AdminUser = Depends(require_role(["owner"])),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    oauth = production_oauth(user.tenant_id)
    if oauth is None:
        raise HTTPException(404, "Conexão com o iFood indisponível para esta loja.")
    try:
        challenge = unseal(oauth, payload.challenge, ttl=600)
        if (
            challenge.get("purpose") != "authorize" or challenge.get("tenant") != user.tenant_id
            or challenge.get("user") != user.id or challenge.get("client") != oauth.client_id
            or challenge["expires"] <= datetime.now(timezone.utc).timestamp()
        ):
            raise ValueError("Wrong or expired challenge")
    except (InvalidToken, ValueError, KeyError, TypeError):
        raise HTTPException(400, "A autorização expirou. Gere um novo link.") from None

    merchant_id = str(payload.merchant_id)
    if merchant_id.lower() == os.getenv("IFOOD_PILOT_MERCHANT_ID", "").strip().lower():
        raise HTTPException(409, "Use uma loja de produção para esta conexão.")
    current = db.get(IFoodConnection, user.tenant_id)
    if current is not None and current.merchant_id != merchant_id:
        raise HTTPException(409, "Este restaurante já está vinculado a outra loja do iFood.")
    try:
        with httpx.Client(timeout=8) as client:
            tokens, expires = exchange_tokens(client, oauth, {
                "grantType": "authorization_code", "authorizationCode": payload.authorization_code.strip(),
                "authorizationCodeVerifier": challenge["verifier"],
            })
            merchant = client.get(f"{IFOOD_API}/merchant/v1.0/merchants/{merchant_id}", headers={
                "Authorization": f"Bearer {tokens['access']}",
            })
            merchant.raise_for_status()
            details = merchant.json()
            if UUID(details["id"]) != payload.merchant_id:
                raise ValueError("Unexpected iFood merchant")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (400, 401, 403, 404):
            raise HTTPException(400, "O iFood não autorizou o código ou a loja. Confira os dados e gere um novo link.") from None
        raise HTTPException(502, "O iFood não concluiu a autorização. Tente novamente.") from None
    except (httpx.RequestError, ValueError, TypeError, KeyError):
        raise HTTPException(502, "O iFood não concluiu a autorização. Tente novamente.") from None

    current = db.scalar(select(IFoodConnection).where(
        IFoodConnection.tenant_id == user.tenant_id,
    ).execution_options(populate_existing=True).with_for_update())
    if current is not None and current.merchant_id != merchant_id:
        raise HTTPException(409, "Este restaurante já está vinculado a outra loja do iFood.")
    if current is None:
        current = IFoodConnection(tenant_id=user.tenant_id, merchant_id=merchant_id)
        db.add(current)
    current.merchant_name = str(details.get("name") or merchant_id)[:255]
    current.encrypted_tokens = seal(oauth, tokens)
    current.expires_at = expires
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A loja iFood ou o restaurante já foi vinculado. Atualize a página.") from None
    return {"merchant_id": merchant_id}
