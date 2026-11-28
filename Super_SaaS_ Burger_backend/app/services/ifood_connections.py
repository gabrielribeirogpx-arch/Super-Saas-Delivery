import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ifood_connection import IFoodConnection
from app.services.ifood_events import IFOOD_API
from app.services.ifood_orders import utc

OAUTH_URL = f"{IFOOD_API}/authentication/v1.0/oauth"


@dataclass(frozen=True)
class IFoodOAuth:
    client_id: str
    client_secret: str
    encryption: Fernet


def production_oauth(tenant_id: int) -> IFoodOAuth | None:
    allowed = os.getenv("IFOOD_PRODUCTION_TENANT_IDS", "").split(",")
    if str(tenant_id) not in {value.strip() for value in allowed}:
        return None
    if str(tenant_id) == os.getenv("IFOOD_PILOT_TENANT_ID"):
        return None
    client_id = os.getenv("IFOOD_CLIENT_ID", "").strip()
    client_secret = os.getenv("IFOOD_CLIENT_SECRET", "").strip()
    try:
        encryption = Fernet(os.getenv("IFOOD_CONNECTION_KEY", "").strip().encode())
    except ValueError:
        return None
    return IFoodOAuth(client_id, client_secret, encryption) if client_id and client_secret else None


def seal(oauth: IFoodOAuth, payload: dict) -> str:
    return oauth.encryption.encrypt(json.dumps(payload).encode()).decode()


def unseal(oauth: IFoodOAuth, encrypted: str, *, ttl: int | None = None) -> dict:
    return json.loads(oauth.encryption.decrypt(encrypted.encode(), ttl=ttl))


def exchange_tokens(
    client: httpx.Client, oauth: IFoodOAuth, grant: dict, previous_refresh: str | None = None,
) -> tuple[dict, datetime]:
    response = client.post(f"{OAUTH_URL}/token", data={
        "clientId": oauth.client_id, "clientSecret": oauth.client_secret, **grant,
    })
    response.raise_for_status()
    payload = response.json()
    access = payload["accessToken"]
    refresh = payload.get("refreshToken") or previous_refresh
    lifetime = int(payload["expiresIn"])
    if not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh or lifetime <= 0:
        raise ValueError("Invalid iFood token response")
    return {"access": access, "refresh": refresh}, datetime.now(timezone.utc) + timedelta(seconds=lifetime)


def production_access(db: Session, tenant_id: int) -> tuple[str | None, str] | None:
    oauth = production_oauth(tenant_id)
    if oauth is None:
        return None
    connection = db.get(IFoodConnection, tenant_id)
    if connection is None:
        return None
    token = None
    if utc(connection.expires_at) > datetime.now(timezone.utc):
        try:
            token = unseal(oauth, connection.encrypted_tokens)["access"]
        except (InvalidToken, ValueError, KeyError):
            pass
    return token, connection.merchant_id


def refresh_production_access(client: httpx.Client, db: Session, tenant_id: int, oauth: IFoodOAuth) -> tuple[str, str] | None:
    connection = db.scalar(select(IFoodConnection).where(
        IFoodConnection.tenant_id == tenant_id,
    ).with_for_update())
    if connection is None:
        return None
    tokens = unseal(oauth, connection.encrypted_tokens)
    if utc(connection.expires_at) <= datetime.now(timezone.utc) + timedelta(minutes=5):
        tokens, connection.expires_at = exchange_tokens(client, oauth, {
            "grantType": "refresh_token", "refreshToken": tokens["refresh"],
        }, previous_refresh=tokens["refresh"])
        connection.encrypted_tokens = seal(oauth, tokens)
    result = tokens["access"], connection.merchant_id
    db.commit()
    return result
