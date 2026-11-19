"""Owner checkout and authenticated Stripe webhook for SaaS subscriptions."""
from datetime import datetime, timezone
import hashlib
import hmac
import json
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.stripe_config import stripe_settings
from app.deps import require_role
from app.models.billing_event import BillingEventStatus, BillingVerificationStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.billing_common import BillingError, utc
from app.services.billing_inbox import BillingInboxService
from app.services.stripe_billing import StripeBilling, stripe_request
from app.services.subscriptions import SubscriptionActor, SubscriptionService

router = APIRouter(tags=["stripe-billing"])


class StripeCheckoutRequest(BaseModel):
    plan_code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,49}$")


@router.post("/api/admin/billing/stripe/checkout")
def checkout(payload: StripeCheckoutRequest, response: Response, user=Depends(require_role(["owner"])),
             db: Session = Depends(get_db), x_billing_action: str = Header(...)):
    if x_billing_action != "1":
        raise HTTPException(403, "Invalid action")
    try:
        result = StripeBilling(db, stripe_settings()).checkout(user, payload.plan_code)
        db.commit()
        response.headers["Cache-Control"] = "private, no-store"
        return result
    except BillingError:
        db.rollback()
        raise HTTPException(409, "Não foi possível iniciar o pagamento. Atualize a página ou fale com o suporte.") from None


@router.post("/api/admin/billing/stripe/cancel")
def cancel(user=Depends(require_role(["owner"])), db: Session = Depends(get_db),
           x_billing_action: str = Header(...)):
    if x_billing_action != "1":
        raise HTTPException(403, "Invalid action")
    try:
        StripeBilling(db, stripe_settings()).cancel(user)
        db.commit()
        return {"requested": True}
    except BillingError:
        db.rollback()
        raise HTTPException(409, "Não foi possível cancelar a renovação. Tente novamente.") from None


def verify_signature(body: bytes, header: str, secret: str):
    parts = dict(piece.split("=", 1) for piece in header.split(",") if "=" in piece)
    try:
        timestamp = int(parts["t"])
    except (ValueError, KeyError):
        raise HTTPException(401, "Invalid signature") from None
    if abs(time.time() - timestamp) > 300:
        raise HTTPException(401, "Expired signature")
    signed = f"{timestamp}.".encode() + body
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    signatures = [piece[3:] for piece in header.split(",") if piece.startswith("v1=")]
    if not any(hmac.compare_digest(expected, value) for value in signatures):
        raise HTTPException(401, "Invalid signature")


@router.post("/api/webhooks/billing/stripe", status_code=200)
async def webhook(request: Request, db: Session = Depends(get_db)):
    settings = stripe_settings()
    if not settings.enabled:
        raise HTTPException(404, "Not found")
    body = await request.body()
    if len(body) > 65536:
        raise HTTPException(413, "Payload too large")
    verify_signature(body, request.headers.get("stripe-signature", ""), settings.webhook_secret)
    try:
        event = json.loads(body)
        event_id, kind = event["id"], event["type"]
        if event.get("livemode") != (settings.environment == "production") or event.get("account") not in {None, settings.account_id}:
            raise BillingError("stripe_environment_mismatch")
        inbox = BillingInboxService(db)
        receipt = inbox.receive_event(provider="stripe", environment=settings.environment,
            provider_account_id=settings.account_id, provider_event_id=event_id,
            event_type=kind, payload=event, occurred_at=datetime.fromtimestamp(event["created"], timezone.utc))
        if receipt.event.processing_status == BillingEventStatus.PROCESSED:
            db.commit()
            return {"received": True, "duplicate": True}
        if kind in {"customer.subscription.created", "customer.subscription.updated",
                    "customer.subscription.deleted", "invoice.paid", "invoice.payment_failed"}:
            obj = event["data"]["object"]
            remote_id = (obj["id"] if kind.startswith("customer.subscription.") else
                obj.get("subscription") or ((obj.get("parent") or {}).get("subscription_details") or {}).get("subscription"))
            if remote_id:
                remote = stripe_request(settings, "GET", "subscriptions/" + remote_id)
                sub = db.query(Subscription).filter_by(provider="stripe", provider_subscription_id=remote_id).with_for_update().one_or_none()
                if sub is None:
                    # Stripe may deliver before the checkout request commits; retry later.
                    raise BillingError("stripe_subscription_not_bound")
                items = remote.get("items", {}).get("data", [])
                price = (items[0].get("price") or {}).get("id") if len(items) == 1 else None
                allowed = {offer.price_id for offer in settings.offers}
                if remote.get("customer") != sub.provider_customer_id or price not in allowed:
                    raise BillingError("stripe_subscription_mismatch")
                configured_offer = next(offer for offer in settings.offers if offer.price_id == price)
                from app.models.plan import Plan
                current_plan = db.get(Plan, sub.plan_id)
                if current_plan is None or current_plan.code != configured_offer.plan_code:
                    raise BillingError("stripe_plan_mismatch")
                period_start = items[0].get("current_period_start") or remote.get("current_period_start")
                period_end = items[0].get("current_period_end") or remote.get("current_period_end")
                actor = SubscriptionActor(actor_type="provider", origin="stripe", correlation_id=event_id)
                service = SubscriptionService(db)
                if remote["status"] == "active" and period_start and period_end:
                    start = datetime.fromtimestamp(period_start, timezone.utc)
                    end = datetime.fromtimestamp(period_end, timezone.utc)
                    if sub.status in {SubscriptionStatus.CANCELED, SubscriptionStatus.EXPIRED}:
                        service.restart_subscription(sub.tenant_id, sub.id, plan_id=sub.plan_id,
                            provider="stripe", provider_subscription_id=remote_id,
                            current_period_start=start, current_period_end=end, actor=actor)
                    elif sub.status in {SubscriptionStatus.INACTIVE, SubscriptionStatus.PAST_DUE}:
                        service.activate_subscription(sub.tenant_id, sub.id, current_period_start=start,
                            current_period_end=end, actor=actor)
                    elif sub.status == SubscriptionStatus.ACTIVE and (not sub.current_period_end or end > utc(sub.current_period_end)):
                        service.renew_subscription(sub.tenant_id, sub.id, current_period_start=start,
                            current_period_end=end, actor=actor)
                    if remote.get("cancel_at_period_end") and not sub.cancel_at_period_end:
                        service.schedule_cancellation(sub.tenant_id, sub.id, actor=actor)
                elif remote["status"] == "past_due" and sub.status == SubscriptionStatus.ACTIVE:
                    service.mark_past_due(sub.tenant_id, sub.id, actor=actor)
                elif remote["status"] in {"canceled", "unpaid", "incomplete_expired"} and sub.status in {
                    SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE, SubscriptionStatus.INACTIVE}:
                    service.cancel_subscription(sub.tenant_id, sub.id, actor=actor)
                receipt.event.tenant_id = sub.tenant_id
                receipt.event.subscription_id = sub.id
        receipt.event.processing_status = BillingEventStatus.PROCESSED
        receipt.event.verification_status = BillingVerificationStatus.VERIFIED
        receipt.event.processed_at = receipt.event.verified_at = datetime.now(timezone.utc)
        receipt.event.attempt_count += 1
        db.commit()
        return {"received": True, "duplicate": False}
    except (BillingError, KeyError, TypeError, ValueError):
        db.rollback()
        raise HTTPException(503, "Subscription update temporarily unavailable") from None
