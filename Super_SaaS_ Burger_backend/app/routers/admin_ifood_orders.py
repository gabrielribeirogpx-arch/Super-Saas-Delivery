import os
from datetime import datetime, timezone
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.ifood_event import IFoodEvent
from app.models.ifood_order import IFoodOrder
from app.services.ifood_connections import production_access
from app.services.ifood_orders import CONFIRMATION_WINDOW, ORDERS_URL, latest_order_state, pilot_credentials, utc
from app.services.ifood_tracking import fetch_ifood_tracking

router = APIRouter(prefix="/api/admin/ifood-orders", tags=["admin-ifood-orders"])
order_staff = require_role(["admin", "owner", "operator", "cashier"])
READY_SOURCE_STATES = {"CONFIRMED", "PREPARATION_STARTED"}


FINISHED_DELIVERY_STATES = {"DELIVERED", "CONCLUDED", "CANCELLED"}
TRACKABLE_STATES = READY_SOURCE_STATES | {"READY_TO_PICKUP", "DISPATCHED"}
CANCELLABLE_STATES = TRACKABLE_STATES | {"PLACED"}


class IFoodCancellationRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=128)


def _has_merchant_delivery(order: IFoodOrder) -> bool:
    return order.details.get("order_type") == "DELIVERY" and order.details.get("delivered_by") == "MERCHANT"


def _latest_cancellation_failure():
    return select(func.max(IFoodEvent.occurred_at)).where(
        IFoodEvent.tenant_id == IFoodOrder.tenant_id,
        IFoodEvent.merchant_id == IFoodOrder.merchant_id,
        IFoodEvent.order_id == IFoodOrder.order_id,
        IFoodEvent.code == "CANCELLATION_REQUEST_FAILED",
    ).correlate(IFoodOrder).scalar_subquery()


def _cancellation_status(order: IFoodOrder, state: str, failure: datetime | None) -> str | None:
    requested_at = order.cancellation_requested_at
    if requested_at is None or state not in CANCELLABLE_STATES:
        return None
    if failure is not None and utc(failure) >= utc(requested_at):
        return "rejected"
    return "pending"


def _order_access(db: Session, tenant_id: int) -> tuple[str | None, str | None, bool] | None:
    if str(tenant_id) == os.getenv("IFOOD_PILOT_TENANT_ID"):
        try:
            token, _, merchant = pilot_credentials()
            return token, str(merchant), True
        except ValueError:
            return None, None, True
    access = production_access(db, tenant_id)
    return (*access, False) if access else None


def _driver_assigned():
    return select(IFoodEvent.event_id).where(
        IFoodEvent.tenant_id == IFoodOrder.tenant_id,
        IFoodEvent.merchant_id == IFoodOrder.merchant_id,
        IFoodEvent.order_id == IFoodOrder.order_id,
        IFoodEvent.code == "ASSIGN_DRIVER",
    ).correlate(IFoodOrder).exists()


def _partner_deliveries(tenant_id: int, merchant_id: str):
    state = func.coalesce(latest_order_state(), "PLACED")
    assigned = _driver_assigned()
    return select(IFoodOrder, state.label("state"), assigned.label("driver_assigned")).where(
        IFoodOrder.tenant_id == tenant_id,
        IFoodOrder.merchant_id == str(merchant_id),
        IFoodOrder.details["order_type"].as_string() == "DELIVERY",
        IFoodOrder.details["delivered_by"].as_string() == "IFOOD",
    )


@router.get("/deliveries")
def list_partner_deliveries(
    response: Response,
    user: AdminUser = Depends(order_staff),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    access = _order_access(db, user.tenant_id)
    if access is None or access[1] is None:
        return {"enabled": False, "deliveries": []}
    token, merchant, _ = access

    deliveries = _partner_deliveries(user.tenant_id, merchant)
    state = deliveries.selected_columns.state
    rows = db.execute(deliveries.order_by(
        state.in_(FINISHED_DELIVERY_STATES),
        IFoodOrder.created_at.desc(),
        IFoodOrder.order_id,
    ).limit(20)).all()
    return {"enabled": True, "deliveries": [
        {
            "order_id": order.order_id,
            "display_id": order.details["display_id"],
            "state": state,
            "driver_assigned": assigned,
            "ready_pending": state in READY_SOURCE_STATES and order.ready_requested_at is not None,
            "can_track": bool(token) and assigned and state in TRACKABLE_STATES,
        }
        for order, state, assigned in rows
    ]}


@router.get("/{order_id}/tracking")
def track_partner_delivery(
    order_id: UUID,
    response: Response,
    user: AdminUser = Depends(order_staff),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    access = _order_access(db, user.tenant_id)
    if access is None:
        raise HTTPException(404, "Entrega iFood não encontrada.")
    token, merchant, _ = access
    if not token or not merchant:
        raise HTTPException(503, "Conexão com o iFood indisponível.")

    row = db.execute(_partner_deliveries(user.tenant_id, merchant).where(
        IFoodOrder.order_id == str(order_id),
    )).one_or_none()
    if row is None or not row.driver_assigned or row.state not in TRACKABLE_STATES:
        raise HTTPException(404, "Rastreamento indisponível para esta entrega.")
    db.rollback()
    return {"tracking": fetch_ifood_tracking(token, str(order_id))}


@router.get("")
def list_pilot_orders(
    response: Response,
    user: AdminUser = Depends(order_staff),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    access = _order_access(db, user.tenant_id)
    if access is None:
        return {"enabled": False, "orders": []}
    token, merchant, pilot = access

    query = select(IFoodOrder, latest_order_state(), _latest_cancellation_failure()).where(IFoodOrder.tenant_id == user.tenant_id)
    if not pilot:
        query = query.where(IFoodOrder.merchant_id == merchant)
    rows = db.execute(query.order_by(IFoodOrder.created_at.desc()).limit(20)).all()
    now = datetime.now(timezone.utc)
    orders = []
    for order, state, cancellation_failure in rows:
        state = state or "PLACED"
        deadline = utc(order.created_at) + CONFIRMATION_WINDOW
        pending = state == "PLACED" and order.confirmation_requested_at is not None
        ready_pending = state in READY_SOURCE_STATES and order.ready_requested_at is not None
        cancellation = _cancellation_status(order, state, cancellation_failure)
        dispatchable = state == "READY_TO_PICKUP" and _has_merchant_delivery(order)
        dispatch_pending = dispatchable and order.dispatch_requested_at is not None
        orders.append({
            **order.details,
            "order_id": order.order_id,
            "created_at": utc(order.created_at).isoformat(),
            "state": state,
            "confirmation_pending": pending,
            "ready_pending": ready_pending,
            "cancellation_status": cancellation,
            "dispatch_pending": dispatch_pending,
            "can_dispatch": (
                bool(token) and merchant == order.merchant_id and dispatchable
                and not dispatch_pending and cancellation != "pending"
            ),
            "can_cancel": (
                bool(token) and merchant == order.merchant_id
                and state in CANCELLABLE_STATES and cancellation != "pending"
            ),
            "can_mark_ready": (
                bool(token) and merchant == order.merchant_id
                and state in READY_SOURCE_STATES and not ready_pending
            ),
            "confirmation_deadline": deadline.isoformat(),
            "can_confirm": (
                bool(token) and merchant == order.merchant_id
                and state == "PLACED" and not pending and now < deadline
            ),
        })
    return {"enabled": True, "pilot": pilot, "confirmation_available": bool(token), "orders": orders}


def _get_pilot_order(order_id: UUID, user: AdminUser, db: Session, *, lock: bool = True) -> tuple[IFoodOrder, str, str]:
    access = _order_access(db, user.tenant_id)
    if access is None:
        raise HTTPException(404, "Pedido iFood não encontrado.")
    token, merchant, _ = access
    if not token or not merchant:
        raise HTTPException(503, "O envio de ações ao iFood ainda não está habilitado.")

    query = select(IFoodOrder).where(
        IFoodOrder.order_id == str(order_id),
        IFoodOrder.tenant_id == user.tenant_id,
        IFoodOrder.merchant_id == merchant,
    )
    order = db.scalar(query.with_for_update() if lock else query)
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
    order, state, token = _get_pilot_order(order_id, user, db)
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
    order, state, token = _get_pilot_order(order_id, user, db)
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


@router.post("/{order_id}/dispatch", status_code=202)
def dispatch_order(
    order_id: UUID,
    user: AdminUser = Depends(order_staff),
    db: Session = Depends(get_db),
):
    order, state, token = _get_pilot_order(order_id, user, db)
    if not _has_merchant_delivery(order):
        raise HTTPException(409, "O despacho pelo painel está disponível para entrega própria.")
    if state in {"DISPATCHED", "DELIVERED", "CONCLUDED"}:
        return {"dispatch_pending": False}
    if state != "READY_TO_PICKUP":
        raise HTTPException(409, "Aguarde o iFood confirmar que o pedido está pronto para retirada.")
    if order.dispatch_requested_at is not None:
        return {"dispatch_pending": True}
    failure = db.scalar(select(_latest_cancellation_failure()).select_from(IFoodOrder).where(
        IFoodOrder.order_id == order.order_id,
    ))
    if _cancellation_status(order, state, failure) == "pending":
        raise HTTPException(409, "O pedido está aguardando o retorno do cancelamento.")

    _send_order_action(order, token, "dispatch", "O iFood recusou o despacho")
    order.dispatch_requested_at = datetime.now(timezone.utc)
    db.commit()
    return {"dispatch_pending": True}


def _cancellation_reasons(client: httpx.Client, order_id: str, headers: dict) -> list[dict]:
    result = client.get(f"{ORDERS_URL}/{order_id}/cancellationReasons", headers=headers)
    if result.status_code == 204:
        return []
    result.raise_for_status()
    reasons = result.json()["reasons"]
    return [
        {"code": item["code"], "description": item["description"]}
        for item in reasons
        if isinstance(item.get("code"), str) and isinstance(item.get("description"), str)
    ]


@router.get("/{order_id}/cancellation-reasons")
def list_cancellation_reasons(
    order_id: UUID,
    response: Response,
    user: AdminUser = Depends(order_staff),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    order, state, token = _get_pilot_order(order_id, user, db, lock=False)
    if state not in CANCELLABLE_STATES:
        return {"reasons": []}
    remote_id = order.order_id
    db.rollback()
    try:
        with httpx.Client(timeout=8) as client:
            reasons = _cancellation_reasons(client, remote_id, {"Authorization": f"Bearer {token}"})
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(502, "Não foi possível consultar os motivos de cancelamento no iFood.") from None
    return {"reasons": reasons}


@router.post("/{order_id}/cancel", status_code=202)
def request_order_cancellation(
    order_id: UUID,
    payload: IFoodCancellationRequest,
    user: AdminUser = Depends(order_staff),
    db: Session = Depends(get_db),
):
    order, state, token = _get_pilot_order(order_id, user, db)
    if state == "CANCELLED":
        return {"cancellation_status": None}
    if state not in CANCELLABLE_STATES:
        raise HTTPException(409, "O pedido não está disponível para cancelamento.")
    failure = db.scalar(select(_latest_cancellation_failure()).select_from(IFoodOrder).where(
        IFoodOrder.order_id == order.order_id,
    ))
    if _cancellation_status(order, state, failure) == "pending":
        return {"cancellation_status": "pending"}

    headers = {"Authorization": f"Bearer {token}"}
    try:
        with httpx.Client(timeout=8) as client:
            reasons = _cancellation_reasons(client, order.order_id, headers)
            if payload.reason not in {reason["code"] for reason in reasons}:
                raise HTTPException(409, "O motivo não está disponível. Consulte os motivos novamente.")
            requested_at = datetime.now(timezone.utc)
            result = client.post(
                f"{ORDERS_URL}/{order.order_id}/requestCancellation",
                headers=headers,
                json={"reason": payload.reason},
            )
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(502, "Não foi possível enviar o cancelamento ao iFood.") from None
    if result.status_code != 202:
        if result.status_code in (204, 400, 404):
            raise HTTPException(409, "O iFood não aceitou o cancelamento. Confira o estado do pedido e os motivos disponíveis.")
        raise HTTPException(502, f"O iFood recusou o cancelamento (HTTP {result.status_code}).")
    order.cancellation_requested_at = requested_at
    db.commit()
    return {"cancellation_status": "pending"}
