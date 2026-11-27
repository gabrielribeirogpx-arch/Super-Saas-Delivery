import os
from datetime import datetime, timezone
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.ifood_order import IFoodOrder
from app.services.ifood_orders import CONFIRMATION_WINDOW, ORDERS_URL, latest_order_state, pilot_credentials, utc

router = APIRouter(prefix="/api/admin/ifood-orders", tags=["admin-ifood-orders"])
order_staff = require_role(["admin", "owner", "operator", "cashier"])
READY_SOURCE_STATES = {"CONFIRMED", "PREPARATION_STARTED"}


@router.get("")
def list_pilot_orders(
    response: Response,
    user: AdminUser = Depends(order_staff),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    if str(user.tenant_id) != os.getenv("IFOOD_PILOT_TENANT_ID"):
        return {"enabled": False, "orders": []}

    try:
        _, _, merchant = pilot_credentials()
    except ValueError:
        merchant = None

    rows = db.execute(
        select(IFoodOrder, latest_order_state())
        .where(IFoodOrder.tenant_id == user.tenant_id)
        .order_by(IFoodOrder.created_at.desc())
        .limit(20)
    ).all()
    now = datetime.now(timezone.utc)
    orders = []
    for order, state in rows:
        state = state or "PLACED"
        deadline = utc(order.created_at) + CONFIRMATION_WINDOW
        pending = state == "PLACED" and order.confirmation_requested_at is not None
        ready_pending = state in READY_SOURCE_STATES and order.ready_requested_at is not None
        orders.append({
            **order.details,
            "order_id": order.order_id,
            "created_at": utc(order.created_at).isoformat(),
            "state": state,
            "confirmation_pending": pending,
            "ready_pending": ready_pending,
            "can_mark_ready": (
                merchant is not None and str(merchant) == order.merchant_id
                and state in READY_SOURCE_STATES and not ready_pending
            ),
            "confirmation_deadline": deadline.isoformat(),
            "can_confirm": (
                merchant is not None and str(merchant) == order.merchant_id
                and state == "PLACED" and not pending and now < deadline
            ),
        })
    return {"enabled": True, "confirmation_available": merchant is not None, "orders": orders}


def _locked_pilot_order(order_id: UUID, user: AdminUser, db: Session) -> tuple[IFoodOrder, str, str]:
    if str(user.tenant_id) != os.getenv("IFOOD_PILOT_TENANT_ID"):
        raise HTTPException(404, "Pedido iFood não encontrado.")
    try:
        token, tenant_id, merchant = pilot_credentials()
    except ValueError:
        raise HTTPException(503, "O envio de ações ao iFood ainda não está habilitado.") from None

    order = db.scalar(
        select(IFoodOrder)
        .where(
            IFoodOrder.order_id == str(order_id),
            IFoodOrder.tenant_id == tenant_id,
            IFoodOrder.merchant_id == str(merchant),
        )
        .with_for_update()
    )
    if order is None:
        raise HTTPException(404, "Pedido iFood não encontrado.")
    state = db.scalar(select(latest_order_state()).select_from(IFoodOrder).where(
        IFoodOrder.order_id == order.order_id,
    )) or "PLACED"
    return order, state, token


def _send_order_action(order: IFoodOrder, token: str, action: str, failure_message: str) -> None:
    try:
        with httpx.Client(timeout=8) as client:
            result = client.post(
                f"{ORDERS_URL}/{order.order_id}/{action}",
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError:
        raise HTTPException(502, "O iFood não respondeu. Atualize os pedidos antes de tentar novamente.") from None
    if result.status_code != 202:
        raise HTTPException(502, f"{failure_message} (HTTP {result.status_code}).")


@router.post("/{order_id}/confirm", status_code=202)
def confirm_pilot_order(
    order_id: UUID,
    user: AdminUser = Depends(order_staff),
    db: Session = Depends(get_db),
):
    order, state, token = _locked_pilot_order(order_id, user, db)
    if state != "PLACED":
        raise HTTPException(409, "O status do pedido mudou no iFood.")
    if order.confirmation_requested_at:
        return {"confirmation_pending": True}
    if datetime.now(timezone.utc) >= utc(order.created_at) + CONFIRMATION_WINDOW:
        raise HTTPException(409, "O prazo de confirmação do iFood terminou.")

    _send_order_action(order, token, "confirm", "O iFood recusou a solicitação de confirmação")
    order.confirmation_requested_at = datetime.now(timezone.utc)
    db.commit()
    return {"confirmation_pending": True}


@router.post("/{order_id}/ready", status_code=202)
def mark_pilot_order_ready(
    order_id: UUID,
    user: AdminUser = Depends(order_staff),
    db: Session = Depends(get_db),
):
    order, state, token = _locked_pilot_order(order_id, user, db)
    if state == "READY_TO_PICKUP":
        return {"ready_pending": False}
    if state not in READY_SOURCE_STATES:
        raise HTTPException(409, "O pedido precisa estar confirmado para avisar que está pronto.")
    if order.ready_requested_at is not None:
        return {"ready_pending": True}

    _send_order_action(order, token, "readyToPickup", "O iFood recusou o aviso de pedido pronto")
    order.ready_requested_at = datetime.now(timezone.utc)
    db.commit()
    return {"ready_pending": True}
