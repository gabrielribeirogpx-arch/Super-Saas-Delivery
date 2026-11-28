"""Poll orders for authorized production restaurants every 30 seconds."""

import logging
import time
from uuid import UUID

import httpx
from cryptography.fernet import InvalidToken
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import SessionLocal
from app.models.ifood_connection import IFoodConnection
from app.services.ifood_connections import production_oauth, refresh_production_access
from app.services.ifood_auto_accept import auto_accept_ifood_orders
from app.services.ifood_events import poll_ifood_events
from app.services.ifood_orders import import_ifood_orders

logger = logging.getLogger("ifood_production")


def poll_connections(client: httpx.Client) -> None:
    with SessionLocal() as db:
        tenants = db.scalars(select(IFoodConnection.tenant_id)).all()
    for tenant_id in tenants:
        oauth = production_oauth(tenant_id)
        if oauth is None:
            continue
        try:
            with SessionLocal() as db:
                access = refresh_production_access(client, db, tenant_id, oauth)
                if access is None:
                    continue
                token, merchant_id = access
                merchant = UUID(merchant_id)
                count = poll_ifood_events(
                    client, db, access_token=token, tenant_id=tenant_id, merchant_id=merchant,
                )
                imported = import_ifood_orders(client, db, token, tenant_id, merchant, test_orders=False)
                accepted = auto_accept_ifood_orders(db, token, tenant_id, merchant, wait_for_new_orders=bool(imported))
                if accepted:
                    logger.info("Automatically requested confirmation of %d iFood orders", accepted)
                if count or imported:
                    logger.info("Tenant %d: %d iFood events, %d orders imported", tenant_id, count, imported)
        except httpx.HTTPStatusError as exc:
            logger.warning("Tenant %d: iFood HTTP %d", tenant_id, exc.response.status_code)
        except (httpx.RequestError, InvalidToken, ValueError, KeyError, TypeError, SQLAlchemyError) as exc:
            logger.warning("Tenant %d: iFood cycle failed (%s)", tenant_id, type(exc).__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with httpx.Client(timeout=10) as client:
        while True:
            started = time.monotonic()
            try:
                poll_connections(client)
            except SQLAlchemyError:
                logger.warning("Could not load iFood connections; retrying")
            time.sleep(max(1, 30 - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
