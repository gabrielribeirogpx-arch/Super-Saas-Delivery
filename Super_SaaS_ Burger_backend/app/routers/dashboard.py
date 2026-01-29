from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.finance import CashMovement, OrderPayment
from app.models.inventory import InventoryItem, InventoryMovement
from app.models.order import Order
from app.models.order_item import OrderItem
from app.services.inventory import count_low_stock


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _parse_date(value: str) -> date:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.date()
    except ValueError:
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Data inválida") from exc


def _parse_datetime(value: str, is_end: bool) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed
    except ValueError:
        try:
            parsed_date = date.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Data inválida") from exc
        return datetime.combine(parsed_date, time.max if is_end else time.min)


def _resolve_range(
    start_str: str | None,
    end_str: str | None,
    default_start: datetime,
    default_end: datetime,
) -> tuple[datetime, datetime]:
    if not start_str and not end_str:
        return default_start, default_end

    start = _parse_datetime(start_str, is_end=False) if start_str else None
    end = _parse_datetime(end_str, is_end=True) if end_str else None

    if not start:
        start = datetime.combine(_parse_date(end_str), time.min) if end_str else default_start
    if not end:
        end = default_end

    if start > end:
        raise HTTPException(status_code=400, detail="Intervalo inválido")

    return start, end


def _today_range() -> tuple[datetime, datetime]:
    now = datetime.now()
    return datetime.combine(now.date(), time.min), now


def _last_days_range(days: int) -> tuple[datetime, datetime]:
    now = datetime.now()
    start_date = now.date() - timedelta(days=days - 1)
    return datetime.combine(start_date, time.min), now


def _order_total_expression() -> Any:
    return func.coalesce(Order.total_cents, Order.valor_total, 0)


@router.get("/overview")
def dashboard_overview(
    tenant_id: int = Query(...),
    de: str | None = Query(None),
    para: str | None = Query(None),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator", "cashier"])),
):
    default_start, default_end = _today_range()
    start, end = _resolve_range(de, para, default_start, default_end)

    gross_sales_cents = (
        db.query(func.coalesce(func.sum(_order_total_expression()), 0))
        .filter(
            Order.tenant_id == tenant_id,
            Order.created_at >= start,
            Order.created_at <= end,
        )
        .scalar()
        or 0
    )

    orders_count = (
        db.query(func.count(Order.id))
        .filter(
            Order.tenant_id == tenant_id,
            Order.created_at >= start,
            Order.created_at <= end,
        )
        .scalar()
        or 0
    )

    paid_orders_count = (
        db.query(func.count(func.distinct(OrderPayment.order_id)))
        .join(Order, Order.id == OrderPayment.order_id)
        .filter(
            Order.tenant_id == tenant_id,
            Order.created_at >= start,
            Order.created_at <= end,
            OrderPayment.status == "paid",
        )
        .scalar()
        or 0
    )

    open_orders_count = (
        db.query(func.count(Order.id))
        .filter(
            Order.tenant_id == tenant_id,
            Order.created_at >= start,
            Order.created_at <= end,
            Order.status != "ENTREGUE",
        )
        .scalar()
        or 0
    )

    net_cash_cents = (
        db.query(
            func.coalesce(
                func.sum(
                    case(
                        (CashMovement.type == "in", CashMovement.amount_cents),
                        else_=-CashMovement.amount_cents,
                    )
                ),
                0,
            )
        )
        .filter(
            CashMovement.tenant_id == tenant_id,
            CashMovement.occurred_at >= start,
            CashMovement.occurred_at <= end,
        )
        .scalar()
        or 0
    )

    cogs_movements = (
        db.query(InventoryMovement, InventoryItem)
        .join(InventoryItem, InventoryItem.id == InventoryMovement.inventory_item_id)
        .filter(
            InventoryMovement.tenant_id == tenant_id,
            InventoryMovement.type == "OUT",
            InventoryMovement.reason == "sale",
            InventoryMovement.created_at >= start,
            InventoryMovement.created_at <= end,
        )
        .all()
    )
    cogs_cents = 0
    for movement, item in cogs_movements:
        cost_cents = int(item.cost_cents or 0)
        quantity = float(movement.quantity or 0)
        cogs_cents += int(round(quantity * cost_cents))

    gross_profit_cents = int(gross_sales_cents) - int(cogs_cents)
    low_stock_count = count_low_stock(db, tenant_id)

    payment_time = func.coalesce(OrderPayment.paid_at, OrderPayment.created_at)
    payment_breakdown = (
        db.query(
            OrderPayment.method.label("method"),
            func.coalesce(func.sum(OrderPayment.amount_cents), 0).label("total_cents"),
            func.count(OrderPayment.id).label("count"),
        )
        .filter(
            OrderPayment.tenant_id == tenant_id,
            OrderPayment.status == "paid",
            payment_time >= start,
            payment_time <= end,
        )
        .group_by(OrderPayment.method)
        .order_by(func.sum(OrderPayment.amount_cents).desc())
        .all()
    )

    payment_method_breakdown = [
        {
            "method": row.method,
            "total_cents": int(row.total_cents or 0),
            "count": int(row.count or 0),
        }
        for row in payment_breakdown
    ]

    avg_ticket_cents = int(gross_sales_cents / orders_count) if orders_count else 0
    last_updated = datetime.utcnow()

    return {
        "gross_sales_cents": int(gross_sales_cents),
        "net_cash_cents": int(net_cash_cents),
        "orders_count": int(orders_count),
        "paid_orders_count": int(paid_orders_count),
        "open_orders_count": int(open_orders_count),
        "avg_ticket_cents": avg_ticket_cents,
        "cogs_cents": int(cogs_cents),
        "gross_profit_cents": int(gross_profit_cents),
        "low_stock_count": int(low_stock_count),
        "payment_method_breakdown": payment_method_breakdown,
        "last_updated": last_updated.isoformat(),
        "last_updated_str": last_updated.strftime("%H:%M:%S"),
    }


@router.get("/timeseries")
def dashboard_timeseries(
    tenant_id: int = Query(...),
    de: str | None = Query(None),
    para: str | None = Query(None),
    bucket: str = Query("day"),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator", "cashier"])),
):
    if bucket != "day":
        raise HTTPException(status_code=400, detail="Bucket inválido")

    default_start, default_end = _last_days_range(7)
    start, end = _resolve_range(de, para, default_start, default_end)

    order_rows = (
        db.query(
            func.date(Order.created_at).label("day"),
            func.coalesce(func.sum(_order_total_expression()), 0).label("gross_sales_cents"),
            func.count(Order.id).label("orders_count"),
        )
        .filter(
            Order.tenant_id == tenant_id,
            Order.created_at >= start,
            Order.created_at <= end,
        )
        .group_by(func.date(Order.created_at))
        .all()
    )

    cash_rows = (
        db.query(
            func.date(CashMovement.occurred_at).label("day"),
            func.coalesce(
                func.sum(
                    case(
                        (CashMovement.type == "in", CashMovement.amount_cents),
                        else_=-CashMovement.amount_cents,
                    )
                ),
                0,
            ).label("net_cash_cents"),
        )
        .filter(
            CashMovement.tenant_id == tenant_id,
            CashMovement.occurred_at >= start,
            CashMovement.occurred_at <= end,
        )
        .group_by(func.date(CashMovement.occurred_at))
        .all()
    )

    orders_map = {row.day: row for row in order_rows}
    cash_map = {row.day: row for row in cash_rows}

    points: List[Dict[str, Any]] = []
    current = start.date()
    end_date = end.date()
    while current <= end_date:
        key = current.isoformat()
        order_row = orders_map.get(key)
        cash_row = cash_map.get(key)
        points.append(
            {
                "date": key,
                "gross_sales_cents": int(order_row.gross_sales_cents) if order_row else 0,
                "orders_count": int(order_row.orders_count) if order_row else 0,
                "net_cash_cents": int(cash_row.net_cash_cents) if cash_row else 0,
            }
        )
        current += timedelta(days=1)

    return {"points": points}


def _fallback_top_items(
    tenant_id: int,
    start: datetime,
    end: datetime,
    limit: int,
    db: Session,
) -> List[Dict[str, Any]]:
    import json

    orders = (
        db.query(Order)
        .filter(
            Order.tenant_id == tenant_id,
            Order.created_at >= start,
            Order.created_at <= end,
        )
        .all()
    )
    totals: Dict[str, Dict[str, int]] = {}
    for order in orders:
        try:
            items = json.loads(order.items_json or "[]")
        except Exception:
            items = []
        if not isinstance(items, list):
            continue
        for item in items:
            name = str(item.get("name", "") or "").strip()
            if not name:
                continue
            qty = int(item.get("quantity", 0) or 0)
            total_cents = int(item.get("subtotal_cents", 0) or 0)
            if name not in totals:
                totals[name] = {"qty": 0, "total_cents": 0}
            totals[name]["qty"] += qty
            totals[name]["total_cents"] += total_cents

    sorted_items = sorted(totals.items(), key=lambda item: item[1]["total_cents"], reverse=True)
    return [
        {"name": name, "qty": values["qty"], "total_cents": values["total_cents"]}
        for name, values in sorted_items[:limit]
    ]


@router.get("/top-items")
def dashboard_top_items(
    tenant_id: int = Query(...),
    de: str | None = Query(None),
    para: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator", "cashier"])),
):
    default_start, default_end = _today_range()
    start, end = _resolve_range(de, para, default_start, default_end)

    rows = (
        db.query(
            OrderItem.name.label("name"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("qty"),
            func.coalesce(func.sum(OrderItem.subtotal_cents), 0).label("total_cents"),
        )
        .filter(
            OrderItem.tenant_id == tenant_id,
            OrderItem.created_at >= start,
            OrderItem.created_at <= end,
        )
        .group_by(OrderItem.name)
        .order_by(func.sum(OrderItem.subtotal_cents).desc())
        .limit(limit)
        .all()
    )

    items = [
        {"name": row.name, "qty": int(row.qty or 0), "total_cents": int(row.total_cents or 0)}
        for row in rows
        if row.name
    ]

    if not items:
        items = _fallback_top_items(tenant_id=tenant_id, start=start, end=end, limit=limit, db=db)

    return {"items": items}


@router.get("/recent-orders")
def dashboard_recent_orders(
    tenant_id: int = Query(...),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator", "cashier"])),
):
    orders = (
        db.query(Order)
        .filter(Order.tenant_id == tenant_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .all()
    )

    if not orders:
        return {"orders": []}

    order_ids = [order.id for order in orders]
    payments = (
        db.query(OrderPayment)
        .filter(OrderPayment.order_id.in_(order_ids), OrderPayment.tenant_id == tenant_id)
        .order_by(OrderPayment.order_id.asc(), OrderPayment.created_at.desc())
        .all()
    )

    latest_payment: Dict[int, OrderPayment] = {}
    for payment in payments:
        if payment.order_id not in latest_payment:
            latest_payment[payment.order_id] = payment

    response_orders = []
    for order in orders:
        payment = latest_payment.get(order.id)
        response_orders.append(
            {
                "id": order.id,
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "status": order.status,
                "total_cents": int(order.total_cents or order.valor_total or 0),
                "payment_status": payment.status if payment else "pending",
                "payment_method": payment.method if payment else order.forma_pagamento,
            }
        )

    return {"orders": response_orders}
