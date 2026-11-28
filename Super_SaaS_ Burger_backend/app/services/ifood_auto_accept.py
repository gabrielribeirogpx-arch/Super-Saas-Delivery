import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ifood_auto_accept import IFoodAutoAccept
from app.models.ifood_order import IFoodOrder
from app.routers.admin_ifood_orders import (
    _cancellation_status, _latest_cancellation_failure, send_ifood_confirmation,
)
from app.services.ifood_orders import CONFIRMATION_WINDOW, latest_order_state, utc

logger = logging.getLogger(__name__)


def auto_accept_ifood_orders(db: Session, token: str, tenant_id: int, merchant_id: UUID) -> int:
    merchant = str(merchant_id)
    preference = db.get(IFoodAutoAccept, (tenant_id, merchant))
    if preference is None or preference.enabled_at is None:
        return 0
    threshold = max(utc(preference.enabled_at), datetime.now(timezone.utc) - CONFIRMATION_WINDOW)
    candidates = db.scalars(select(IFoodOrder.order_id).where(
        IFoodOrder.tenant_id == tenant_id,
        IFoodOrder.merchant_id == merchant,
        IFoodOrder.created_at >= threshold,
        IFoodOrder.confirmation_requested_at.is_(None),
        latest_order_state() == "PLACED",
    ).order_by(IFoodOrder.created_at, IFoodOrder.order_id).limit(20)).all()
    db.rollback()
    accepted = 0
    for order_id in candidates:
        order = db.scalar(select(IFoodOrder).where(
            IFoodOrder.order_id == order_id, IFoodOrder.tenant_id == tenant_id,
            IFoodOrder.merchant_id == merchant,
        ).with_for_update())
        if order is None or order.confirmation_requested_at is not None:
            db.rollback()
            continue
        preference = db.get(IFoodAutoAccept, (tenant_id, merchant), with_for_update=True)
        if preference is None or preference.enabled_at is None:
            db.rollback()
            break
        if utc(order.created_at) < utc(preference.enabled_at):
            db.rollback()
            continue
        state, failure = db.execute(select(latest_order_state(), _latest_cancellation_failure()).select_from(
            IFoodOrder,
        ).where(IFoodOrder.order_id == order_id)).one()
        if state != "PLACED" or _cancellation_status(order, state, failure) == "pending":
            db.rollback()
            continue
        try:
            send_ifood_confirmation(order, state, token)
            db.commit()
            accepted += 1
        except HTTPException as exc:
            db.rollback()
            logger.warning("iFood automatic confirmation did not complete for tenant %d (HTTP %d)", tenant_id, exc.status_code)
    return accepted
