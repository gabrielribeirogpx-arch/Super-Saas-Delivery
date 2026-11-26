from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date, String, case, cast, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_request_tenant_id, require_role
from app.models.admin_user import AdminUser
from app.models.finance import CashMovement, OrderPayment
from app.models.inventory import InventoryItem, InventoryMovement
from app.models.order import Order
from app.models.order_item import OrderItem
from app.services.inventory import count_low_stock


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        localized = value.replace(tzinfo=BRAZIL_TZ)
    else:
        localized = value.astimezone(BRAZIL_TZ)
    return localized.astimezone(timezone.utc)


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
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=BRAZIL_TZ)
        if is_end and "T" not in value and " " not in value:
            parsed = datetime.combine(parsed.date() + timedelta(days=1), time.min, tzinfo=BRAZIL_TZ)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        try:
            parsed_date = date.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Data inválida") from exc
        target_date = parsed_date + timedelta(days=1) if is_end else parsed_date
        return _to_utc(datetime.combine(target_date, time.min))


def _resolve_range(
    start_str: str | None,
    end_str: str | None,
    fallback_start_str: str | None,
    fallback_end_str: str | None,
    default_start: datetime,
    default_end: datetime,
) -> tuple[datetime, datetime]:
    start_value = start_str or fallback_start_str
    end_value = end_str or fallback_end_str

    if not start_value and not end_value:
        return default_start, default_end

    start = _parse_datetime(start_value, is_end=False) if start_value else None
    end = _parse_datetime(end_value, is_end=True) if end_value else None

    if not start:
        start = _to_utc(datetime.combine(_parse_date(end_value), time.min)) if end_value else default_start
    if not end:
        end = default_end

    if start >= end:
        raise HTTPException(status_code=400, detail="Intervalo inválido")

    return start, end


def _today_range() -> tuple[datetime, datetime]:
    now = datetime.now(BRAZIL_TZ)
    start = datetime.combine(now.date(), time.min, tzinfo=BRAZIL_TZ)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def _last_days_range(days: int) -> tuple[datetime, datetime]:
    now = datetime.now(BRAZIL_TZ)
    start_date = now.date() - timedelta(days=days - 1)
    start = datetime.combine(start_date, time.min, tzinfo=BRAZIL_TZ)
    end = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=BRAZIL_TZ)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def _order_total_expression() -> Any:
    return func.coalesce(Order.total_cents, Order.valor_total, 0)


@router.get("/overview")
def dashboard_overview(
    tenant_id: int = Depends(get_request_tenant_id),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    de: str | None = Query(None),
    para: str | None = Query(None),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator", "cashier"])),
):
    default_start, default_end = _today_range()
    start, end = _resolve_range(start_date, end_date, de, para, default_start, default_end)

    gross_sales_cents = (
        db.query(func.coalesce(func.sum(_order_total_expression()), 0))
        .filter(
            Order.tenant_id == tenant_id,
            Order.created_at >= start,
            Order.created_at < end,
        )
        .scalar()
        or 0
    )

    orders_count = (
        db.query(func.count(Order.id))
        .filter(
            Order.tenant_id == tenant_id,
            Order.created_at >= start,
            Order.created_at < end,
        )
        .scalar()
        or 0
    )

    customer_identifier = func.coalesce(
        cast(Order.customer_id, String),
        Order.customer_phone,
        Order.cliente_telefone,
    )
    active_customers = (
        db.query(func.count(func.distinct(customer_identifier)))
        .filter(
            Order.tenant_id == tenant_id,
            Order.created_at >= start,
            Order.created_at < end,
            customer_identifier.isnot(None),
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
            Order.created_at < end,
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
            Order.created_at < end,
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
            CashMovement.occurred_at < end,
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
            InventoryMovement.created_at < end,
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
            payment_time < end,
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
        "active_customers": int(active_customers),
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


def _bucket_totals(db: Session, timestamp, tenant_scope, start: datetime, end: datetime, cents, bucket: str):
    filters = (tenant_scope, timestamp >= start, timestamp < end)
    if db.get_bind().dialect.name == "postgresql":
        # Convert the instant before extracting the date, regardless of session TimeZone.
        local_timestamp = func.timezone(BRAZIL_TZ.key, timestamp)
        key = func.date_trunc("hour", local_timestamp) if bucket == "hour" else cast(local_timestamp, Date)
        rows = (
            db.query(key, func.sum(cents), func.count())
            .filter(*filters)
            .group_by(key)
        )
        return {key: (int(total or 0), int(count)) for key, total, count in rows}

    # SQLite returns UTC timestamps without tzinfo and has no IANA timezone support.
    # Stream only the needed columns so historical daylight saving is handled as well.
    totals = defaultdict(lambda: (0, 0))
    for instant, amount in db.query(timestamp, cents).filter(*filters).yield_per(1000):
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=timezone.utc)
        local = instant.astimezone(BRAZIL_TZ).replace(tzinfo=None)
        key = local.replace(minute=0, second=0, microsecond=0) if bucket == "hour" else local.date()
        total, count = totals[key]
        totals[key] = (total + int(amount or 0), count + 1)
    return totals


@router.get("/timeseries")
def dashboard_timeseries(
    tenant_id: int = Depends(get_request_tenant_id),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    de: str | None = Query(None),
    para: str | None = Query(None),
    bucket: str = Query("day"),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator", "cashier"])),
):
    if bucket not in ("day", "hour"):
        raise HTTPException(status_code=400, detail="Bucket inválido")

    default_start, default_end = _last_days_range(7)
    start, end = _resolve_range(start_date, end_date, de, para, default_start, default_end)

    first_local = start.astimezone(BRAZIL_TZ).replace(tzinfo=None)
    last_local = (end - timedelta(microseconds=1)).astimezone(BRAZIL_TZ).replace(tzinfo=None)
    if bucket == "hour" and first_local.date() != last_local.date():
        raise HTTPException(status_code=400, detail="A série por hora exige um único dia")

    orders = _bucket_totals(
        db, Order.created_at, Order.tenant_id == tenant_id,
        start, end, _order_total_expression(), bucket,
    )
    cash = _bucket_totals(
        db, CashMovement.occurred_at, CashMovement.tenant_id == tenant_id,
        start, end, case(
            (CashMovement.type == "in", CashMovement.amount_cents),
            else_=-CashMovement.amount_cents,
        ), bucket,
    )

    points: List[Dict[str, Any]] = []
    if bucket == "hour":
        current = first_local.replace(minute=0, second=0, microsecond=0)
        last = last_local.replace(minute=0, second=0, microsecond=0)
        step = timedelta(hours=1)
    else:
        current = first_local.date()
        last = last_local.date()
        step = timedelta(days=1)
    while current <= last:
        gross_sales, orders_count = orders.get(current, (0, 0))
        net_cash, _ = cash.get(current, (0, 0))
        points.append(
            {
                "date": current.isoformat(),
                "gross_sales_cents": gross_sales,
                "orders_count": orders_count,
                "net_cash_cents": net_cash,
            }
        )
        current += step

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
            Order.created_at < end,
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
    tenant_id: int = Depends(get_request_tenant_id),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    de: str | None = Query(None),
    para: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator", "cashier"])),
):
    default_start, default_end = _today_range()
    start, end = _resolve_range(start_date, end_date, de, para, default_start, default_end)

    rows = (
        db.query(
            OrderItem.name.label("name"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("qty"),
            func.coalesce(func.sum(OrderItem.subtotal_cents), 0).label("total_cents"),
        )
        .filter(
            OrderItem.tenant_id == tenant_id,
            OrderItem.created_at >= start,
            OrderItem.created_at < end,
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
    tenant_id: int = Depends(get_request_tenant_id),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    de: str | None = Query(None),
    para: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator", "cashier"])),
):
    default_start, default_end = _last_days_range(7)
    start, end = _resolve_range(start_date, end_date, de, para, default_start, default_end)

    orders = (
        db.query(Order)
        .filter(
            Order.tenant_id == tenant_id,
            Order.created_at >= start,
            Order.created_at < end,
        )
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
                "daily_order_number": order.daily_order_number,
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "status": order.status,
                "total_cents": int(order.total_cents or order.valor_total or 0),
                "payment_status": payment.status if payment else "pending",
                "payment_method": payment.method if payment else order.forma_pagamento,
            }
        )

    return {"orders": response_orders}
