"""Authenticated tenant administrators review only sanitized billing evidence."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.core.kiwify_config import kiwify_settings
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.services.billing_common import BillingConflict, BillingError
from app.services.billing_manual_review import BillingManualReviewService, ReviewNotFound
from app.services.kiwify_verification import KiwifyVerificationService

router = APIRouter(prefix="/api/admin/billing/reviews", tags=["admin-billing-reviews"])


def review_verifier():
    settings = kiwify_settings()
    if not settings.enabled:
        yield None
        return
    service = KiwifyVerificationService(SessionLocal, settings)
    try:
        yield service
    finally:
        service.source.close()


class BillingReviewRead(BaseModel):
    billing_event_id: int
    provider: str
    event_type: str
    order_id: str | None
    external_subscription_id: str | None
    product_id: str | None
    external_offer_id: str | None
    candidate_plan_id: int | None
    candidate_plan_name: str | None
    candidate_tenant_id: int | None
    verification_status: str
    received_at: datetime
    occurred_at: datetime | None
    sale_checked_at: datetime | None
    sale_status: str | None
    period_start: datetime | None
    period_end: datetime | None
    reason: str
    can_approve: bool
    access_pending_period: bool
    approval_blockers: list[str]
    decision: str | None
    decided_by: int | None
    decided_at: datetime | None
    rejection_reason: str | None


class BillingReviewReject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal["incorrect_binding", "incorrect_plan", "duplicate_sale", "invalid_sale", "insufficient_evidence"]


def _error(exc):
    code = 404 if isinstance(exc, ReviewNotFound) else 409 if isinstance(exc, BillingConflict) else 403 if str(exc) == "review_forbidden" else 422
    raise HTTPException(status_code=code, detail=str(exc)) from None


@router.get("", response_model=list[BillingReviewRead])
def list_reviews(event_type: str | None = Query(None, max_length=100), from_date: datetime | None = None,
    to_date: datetime | None = None, plan_id: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
    user: AdminUser = Depends(require_role(["admin"])), db: Session = Depends(get_db)):
    try:
        return BillingManualReviewService(db).list(user, event_type=event_type, from_date=from_date,
            to_date=to_date, plan_id=plan_id, limit=limit, offset=offset)
    except BillingError as exc:
        _error(exc)


@router.get("/{event_id}", response_model=BillingReviewRead)
def review_detail(event_id: int, user: AdminUser = Depends(require_role(["admin"])), db: Session = Depends(get_db)):
    try:
        return BillingManualReviewService(db).detail(event_id, user)
    except BillingError as exc:
        _error(exc)


def _decide(db, event_id, user, *, approve, reason=None):
    try:
        result = BillingManualReviewService(db).decide(event_id, user, approve=approve, rejection_reason=reason)
        db.commit()
        return result
    except BillingError as exc:
        db.rollback()
        _error(exc)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=503, detail="review_temporarily_unavailable") from None


@router.post("/{event_id}/approve", response_model=BillingReviewRead)
def approve_review(event_id: int, user: AdminUser = Depends(require_role(["admin"])), db: Session = Depends(get_db),
    x_billing_review: Literal["1"] = Header(...), verifier=Depends(review_verifier)):
    try:
        detail = BillingManualReviewService(db).detail(event_id, user)
        needs_refresh = (detail["verification_status"] == "manual_review" and not detail["decision"]
                         and "sale_evidence_stale_or_missing" in detail["approval_blockers"])
        if needs_refresh and verifier is not None:
            # Release the request read transaction before the leased provider call.
            db.rollback()
            verifier.verify_event(event_id, manual_refresh=True)
    except BillingError as exc:
        db.rollback()
        _error(exc)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=503, detail="review_temporarily_unavailable") from None
    return _decide(db, event_id, user, approve=True)


@router.post("/{event_id}/reject", response_model=BillingReviewRead)
def reject_review(event_id: int, payload: BillingReviewReject,
    user: AdminUser = Depends(require_role(["admin"])), db: Session = Depends(get_db),
    x_billing_review: Literal["1"] = Header(...)):
    return _decide(db, event_id, user, approve=False, reason=payload.reason)
