"""Collect iFood events for an explicitly configured test restaurant."""

import argparse
import logging
import time

import httpx
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import SessionLocal
from app.services.ifood_auto_accept import auto_accept_ifood_orders
from app.services.ifood_events import poll_ifood_events
from app.services.ifood_orders import import_pilot_orders, pilot_credentials

logger = logging.getLogger("ifood_pilot")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true", help="repeat every 30 seconds")
    parser.add_argument("--import-orders", action="store_true", help="import test orders after the database migration")
    options = parser.parse_args()
    try:
        token, tenant_id, merchant_id = pilot_credentials()
    except ValueError as exc:
        parser.error(str(exc))

    logging.basicConfig(level=logging.INFO)
    with httpx.Client(timeout=10) as client:
        while True:
            started = time.monotonic()
            try:
                with SessionLocal() as db:
                    count = poll_ifood_events(
                        client, db, access_token=token, tenant_id=tenant_id, merchant_id=merchant_id,
                    )
                    logger.info("Acknowledged %d iFood events", count)
                    if options.import_orders:
                        imported = import_pilot_orders(client, db, token, tenant_id, merchant_id)
                        accepted = auto_accept_ifood_orders(db, token, tenant_id, merchant_id)
                        if accepted:
                            logger.info("Automatically requested confirmation of %d iFood orders", accepted)
                        if imported:
                            logger.info("Imported %d iFood test orders", imported)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                logger.error("iFood returned HTTP %d", status)
                if not options.watch or (status < 500 and status != 429):
                    raise SystemExit(1) from None
            except SQLAlchemyError:
                logger.error("Could not store iFood orders or events; check the database and migrations")
                if not options.watch:
                    raise SystemExit(1) from None
            except httpx.RequestError:
                logger.error("Could not reach the iFood API")
                if not options.watch:
                    raise SystemExit(1) from None
            if not options.watch:
                break
            time.sleep(max(1, 30 - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
