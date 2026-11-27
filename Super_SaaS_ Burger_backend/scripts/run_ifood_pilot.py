"""Collect iFood events for an explicitly configured test restaurant."""

import argparse
import logging
import os
import time
from uuid import UUID

import httpx

from app.core.database import SessionLocal
from app.services.ifood_events import poll_ifood_events

logger = logging.getLogger("ifood_pilot")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true", help="repeat every 30 seconds")
    options = parser.parse_args()
    if os.getenv("IFOOD_PILOT_ENABLED") != "true":
        parser.error("set IFOOD_PILOT_ENABLED=true for the test environment")
    try:
        token = os.environ["IFOOD_PILOT_ACCESS_TOKEN"].strip()
        merchant_id = UUID(os.environ["IFOOD_PILOT_MERCHANT_ID"])
        tenant_id = int(os.environ["IFOOD_PILOT_TENANT_ID"])
        if not token or tenant_id < 1:
            raise ValueError
    except (KeyError, ValueError):
        parser.error("configure valid pilot token, merchant UUID and tenant ID")

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
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                logger.error("iFood returned HTTP %d", status)
                if not options.watch or (status < 500 and status != 429):
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
