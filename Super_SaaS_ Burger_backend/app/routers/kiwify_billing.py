"""Untrusted ingress: receipt is NOT authentication or entitlement authority."""
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.core.database import get_db
from app.core.kiwify_config import WEBHOOK_PATH, kiwify_settings
from app.core.rate_limiter import InMemoryRateLimiterService
from app.services.billing_common import BillingConflict, BillingError
from app.services.billing_inbox import BillingInboxService
from app.services.kiwify_projection import project_webhook

router = APIRouter()
_limiter = InMemoryRateLimiterService(limit=60)
MAX_BYTES = 64 * 1024


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


def _nonfinite(_):
    raise ValueError()


def _persist(db, settings, payload, projection, identity):
    try:
        with db.begin():
            receipt = BillingInboxService(db).receive_event(provider="kiwify", environment=settings.environment,
                provider_account_id=settings.account_id, provider_event_id=identity, event_type=projection["webhook_event_type"],
                payload=payload, schema_version=2, sanitized_projection=projection)
            created = receipt.created
        return created
    except Exception:
        db.rollback()
        raise


@router.post(WEBHOOK_PATH, response_class=JSONResponse)
async def receive_kiwify(request: Request, db=Depends(get_db), settings=Depends(kiwify_settings)):
    if not settings.enabled:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    decision = _limiter.check(tenant_id="untrusted-kiwify", endpoint=WEBHOOK_PATH)
    if not decision.allowed:
        return JSONResponse({"detail": "Too many requests"}, status_code=429, headers={"Retry-After": str(decision.retry_after_seconds)})
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        return JSONResponse({"detail": "JSON required"}, status_code=415)
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BYTES:
            return JSONResponse({"detail": "Payload too large"}, status_code=413)
        chunks.append(chunk)
    try:
        payload = json.loads(b"".join(chunks).decode("utf-8"), object_pairs_hook=_object, parse_constant=_nonfinite)
        projection, identity = project_webhook(payload)
    except (ValueError, UnicodeError, RecursionError, BillingError):
        return JSONResponse({"detail": "Invalid payload"}, status_code=422)
    try:
        created = await run_in_threadpool(_persist, db, settings, payload, projection, identity)
    except BillingConflict:
        return JSONResponse({"detail": "Event identity conflict"}, status_code=409)
    except (SQLAlchemyError, BillingError):
        return JSONResponse({"detail": "Receipt unavailable"}, status_code=503, headers={"Retry-After": "30"})
    # Never consume signature/query/tenant claims or invoke SubscriptionService.
    return JSONResponse({"received": True, "duplicate": not created}, status_code=202)
