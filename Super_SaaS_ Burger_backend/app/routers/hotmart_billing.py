"""Hotmart v2 authenticated ingress and tenant-owner subscription self service."""
from datetime import datetime, timezone
import hmac
import json
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.hotmart_config import hotmart_settings, WEBHOOK_PATH
from app.core.rate_limiter import InMemoryRateLimiterService
from app.deps import require_role, require_admin_user
from app.services.billing_common import BillingError, BillingConflict
from app.services.billing_inbox import BillingInboxService
from app.services.hotmart_billing import HotmartBilling
from app.services.hotmart_projection import project

router = APIRouter(tags=["hotmart-billing"])
_limiter = InMemoryRateLimiterService()
ROOT = "/api/admin/billing/subscription"

class HotmartFeatureRead(BaseModel):
    code: str
    enabled: bool
    limit: int | None

class PlanFeatureAccessRead(BaseModel):
    allowed: bool
    reason: str
    limit: int | None
    usage: int | None
    effective_until: datetime | None

class PlanAccessRead(BaseModel):
    managed: bool
    active: bool
    features: dict[str, PlanFeatureAccessRead]
class HotmartOfferRead(BaseModel):
    code: str
    name: str
    price_cents: int
    features: list[HotmartFeatureRead]
class HotmartEventRead(BaseModel):
    type: str
    received_at: datetime
    status: str
class HotmartSubscriptionRead(BaseModel):
    enabled: bool
    provider: str | None
    status: str
    plan_name: str | None
    period_end: datetime | None
    cancel_at_period_end: bool
    cancel_pending: bool
    can_cancel: bool
    can_checkout: bool
    checkout_pending: bool
    offers: list[HotmartOfferRead]
    events: list[HotmartEventRead]
class HotmartCheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_code: str = Field(min_length=1,max_length=50)
class HotmartCheckoutRead(BaseModel):
    checkout_url: str
    expires_at: datetime


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result

@router.post(WEBHOOK_PATH, status_code=202)
async def receive_hotmart(request: Request, db: Session = Depends(get_db), settings=Depends(hotmart_settings)):
    if not settings.enabled:
        raise HTTPException(404, "Not found")
    values = request.headers.getlist("x-hotmart-hottok")
    if len(values) != 1 or not hmac.compare_digest(values[0].encode(),settings.hottok.encode()):
        raise HTTPException(401, "Not authenticated")
    decision = _limiter.check(tenant_id="hotmart-ingress",endpoint=WEBHOOK_PATH)
    if not decision.allowed:
        raise HTTPException(429,"Too many requests",headers={"Retry-After":str(decision.retry_after_seconds)})
    if request.headers.get("content-type","").split(";")[0].strip().lower() != "application/json":
        raise HTTPException(415,"JSON required")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body)>65536:
            raise HTTPException(413,"Payload too large")
    try:
        value = json.loads(body, object_pairs_hook=_json_object, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        projection = project(value)
        receipt = BillingInboxService(db).receive_event(provider="hotmart",environment=settings.environment,
            provider_account_id=settings.account_id,provider_event_id=projection["id"],event_type=projection["event"],
            payload=value,schema_version=3,occurred_at=datetime.fromisoformat(projection["occurred_at"]),sanitized_projection=projection)
        db.commit()
        return {"received":True,"duplicate":not receipt.created}
    except BillingConflict:
        db.rollback()
        raise HTTPException(409,"Event identity conflict") from None
    except (BillingError,ValueError,TypeError):
        db.rollback()
        raise HTTPException(422,"Invalid subscription notification") from None
    except Exception:
        db.rollback()
        raise HTTPException(503,"Notification temporarily unavailable") from None

@router.get(ROOT,response_model=HotmartSubscriptionRead)
def subscription(user=Depends(require_role(["owner"])), db: Session=Depends(get_db),settings=Depends(hotmart_settings)):
    return HotmartBilling(db,settings).summary(user)

@router.post(ROOT+"/checkout",response_model=HotmartCheckoutRead)
def checkout(payload:HotmartCheckoutRequest,user=Depends(require_role(["owner"])),db:Session=Depends(get_db),
             settings=Depends(hotmart_settings),x_billing_action: str=Header(...)):
    if x_billing_action!="1":
        raise HTTPException(403,"Invalid action")
    try:
        result=HotmartBilling(db,settings).checkout(user,payload.plan_code)
        db.commit()
        return result
    except BillingError:
        db.rollback()
        raise HTTPException(409,"Não foi possível iniciar a contratação. Confira a assinatura atual ou fale com o suporte.") from None

@router.post(ROOT+"/cancel",response_model=HotmartSubscriptionRead)
def cancel(user=Depends(require_role(["owner"])),db:Session=Depends(get_db),settings=Depends(hotmart_settings),
           x_billing_action: str=Header(...)):
    if x_billing_action!="1":
        raise HTTPException(403,"Invalid action")
    try:
        service=HotmartBilling(db,settings)
        service.request_cancel(user)
        db.commit()
        return service.summary(user)
    except BillingError:
        db.rollback()
        raise HTTPException(409,"Não foi possível solicitar o cancelamento. Atualize a assinatura e tente novamente.") from None


@router.get("/api/admin/billing/access", response_model=PlanAccessRead)
def plan_access(response: Response, user=Depends(require_admin_user), db: Session=Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    from app.services.plan_access import access_summary
    return access_summary(db, user.tenant_id)
