from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.coupon import Coupon
from app.models.marketing import Reward
from app.models.tenant import Tenant
from app.services.loyalty import resolve_reais_por_ponto

router = APIRouter(prefix="/api/admin/marketing", tags=["admin-marketing"])


class LoyaltyConfigPayload(BaseModel):
    points_enabled: bool
    reais_por_ponto: float = Field(..., gt=0)
    points_expiration_days: int | None = Field(default=None, ge=1)


class CouponPayload(BaseModel):
    code: str = Field(..., min_length=1)
    discount_type: Literal["percentage", "fixed"]
    discount_value: float = Field(..., gt=0)
    min_order_value: float | None = Field(default=None, ge=0)
    max_uses: int | None = Field(default=None, ge=1)
    valid_until: datetime | None = None
    active: bool = True


class RewardPayload(BaseModel):
    points_required: int = Field(..., ge=1)
    discount_value: float = Field(..., gt=0)


def _tenant_for_user(db: Session, current_user: AdminUser) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return tenant


@router.get("/loyalty")
def get_loyalty_config(
    current_user: AdminUser = Depends(require_role(["admin", "operator"])),
    db: Session = Depends(get_db),
):
    tenant = _tenant_for_user(db, current_user)
    return {
        "points_enabled": bool(getattr(tenant, "points_enabled", False)),
        "reais_por_ponto": resolve_reais_por_ponto(tenant),
        "points_expiration_days": getattr(tenant, "points_expiration_days", None),
    }


@router.put("/loyalty")
def update_loyalty_config(
    payload: LoyaltyConfigPayload,
    current_user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    tenant = _tenant_for_user(db, current_user)
    tenant.points_enabled = payload.points_enabled
    tenant.reais_por_ponto = Decimal(str(payload.reais_por_ponto))
    tenant.points_expiration_days = payload.points_expiration_days
    db.commit()
    db.refresh(tenant)
    return {
        "points_enabled": bool(tenant.points_enabled),
        "reais_por_ponto": resolve_reais_por_ponto(tenant),
        "points_expiration_days": tenant.points_expiration_days,
    }


@router.get("/coupons")
def list_coupons(
    active: bool | None = Query(default=None),
    current_user: AdminUser = Depends(require_role(["admin", "operator"])),
    db: Session = Depends(get_db),
):
    query = db.query(Coupon).filter(Coupon.tenant_id == current_user.tenant_id)
    if active is not None:
        query = query.filter(Coupon.active.is_(active))
    coupons = query.order_by(Coupon.created_at.desc()).all()
    return [
        {
            "id": coupon.id,
            "tenant_id": coupon.tenant_id,
            "code": coupon.code,
            "discount_type": coupon.discount_type,
            "discount_value": float(coupon.discount_value or 0),
            "min_order_value": float(coupon.min_order_value) if coupon.min_order_value is not None else None,
            "max_uses": coupon.max_uses,
            "valid_until": coupon.valid_until,
            "active": coupon.active,
            "uses_count": coupon.uses_count,
        }
        for coupon in coupons
    ]


@router.post("/coupons")
def create_coupon(
    payload: CouponPayload,
    current_user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    coupon = Coupon(
        tenant_id=current_user.tenant_id,
        code=payload.code.strip().upper(),
        discount_type=payload.discount_type,
        discount_value=Decimal(str(payload.discount_value)),
        min_order_value=Decimal(str(payload.min_order_value)) if payload.min_order_value is not None else None,
        max_uses=payload.max_uses,
        valid_until=payload.valid_until,
        active=payload.active,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return {"id": coupon.id}


@router.get("/rewards")
def list_rewards(
    current_user: AdminUser = Depends(require_role(["admin", "operator"])),
    db: Session = Depends(get_db),
):
    rewards = (
        db.query(Reward)
        .filter(Reward.tenant_id == current_user.tenant_id)
        .order_by(Reward.points_required.asc())
        .all()
    )
    return [
        {
            "id": reward.id,
            "tenant_id": reward.tenant_id,
            "points_required": reward.points_required,
            "discount_value": float(reward.discount_value or 0),
        }
        for reward in rewards
    ]


@router.post("/rewards")
def create_reward(
    payload: RewardPayload,
    current_user: AdminUser = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    reward = Reward(
        tenant_id=current_user.tenant_id,
        points_required=payload.points_required,
        discount_value=Decimal(str(payload.discount_value)),
    )
    db.add(reward)
    db.commit()
    db.refresh(reward)
    return {"id": reward.id}


@router.post("/checkout/apply")
def apply_checkout_promotions(
    customer_id: int,
    order_total: float,
    coupon_code: str | None = None,
    redeem_points: int = 0,
    current_user: AdminUser = Depends(require_role(["admin", "operator"])),
    db: Session = Depends(get_db),
):
    from app.models.customer_points import CustomerPoints

    total = Decimal(str(order_total))
    discount_total = Decimal("0")

    if coupon_code:
        coupon = (
            db.query(Coupon)
            .filter(Coupon.tenant_id == current_user.tenant_id)
            .filter(Coupon.code == coupon_code.strip().upper())
            .filter(Coupon.active.is_(True))
            .first()
        )
        if coupon:
            now = datetime.now(timezone.utc)
            if coupon.valid_until is None or coupon.valid_until.replace(tzinfo=timezone.utc) >= now:
                if coupon.discount_type == "percentage":
                    discount_total += total * (Decimal(str(coupon.discount_value)) / Decimal("100"))
                elif coupon.discount_type == "fixed":
                    discount_total += Decimal(str(coupon.discount_value))

    redeemed_discount = Decimal("0")
    if redeem_points > 0:
        row = (
            db.query(CustomerPoints)
            .filter(CustomerPoints.tenant_id == current_user.tenant_id, CustomerPoints.customer_id == customer_id)
            .first()
        )
        if row is not None and int(row.available_points or 0) > 0:
            usable_points = min(int(row.available_points), int(redeem_points))
            redeemed_discount = Decimal(str(usable_points / 100))
            discount_total += redeemed_discount

    if discount_total > total:
        discount_total = total

    return {
        "order_total": float(total),
        "discount_total": float(discount_total),
        "total_after_discount": float(total - discount_total),
        "redeemed_points_discount": float(redeemed_discount),
    }
