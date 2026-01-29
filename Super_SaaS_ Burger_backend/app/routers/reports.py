from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.finance import CashMovement, OrderPayment
from app.models.inventory import InventoryItem, InventoryMovement, MenuItemIngredient
from app.models.order import Order
from app.models.order_item import OrderItem

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _parse_date(value: str) -> date:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.date()
    except ValueError:
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Data inválida") from exc


def _date_range(from_str: str, to_str: str) -> tuple[datetime, datetime]:
    start_date = _parse_date(from_str)
    end_date = _parse_date(to_str)
    start = datetime.combine(start_date, time.min)
    end = datetime.combine(end_date, time.max)
    if start > end:
        raise HTTPException(status_code=400, detail="Intervalo inválido")
    return start, end


def _payment_time_expression() -> Any:
    return func.coalesce(OrderPayment.paid_at, OrderPayment.created_at)


def _fee_categories_filter():
    categories = ["fee", "taxa", "taxas"]
    return func.lower(CashMovement.category).in_(categories)


def _sum_fees_cents(db: Session, tenant_id: int, start: datetime, end: datetime) -> int:
    fee_count = (
        db.query(func.count(CashMovement.id))
        .filter(
            CashMovement.tenant_id == tenant_id,
            _fee_categories_filter(),
            CashMovement.occurred_at >= start,
            CashMovement.occurred_at <= end,
        )
        .scalar()
        or 0
    )
    if fee_count:
        fee_sum = (
            db.query(func.coalesce(func.sum(CashMovement.amount_cents), 0))
            .filter(
                CashMovement.tenant_id == tenant_id,
                _fee_categories_filter(),
                CashMovement.occurred_at >= start,
                CashMovement.occurred_at <= end,
            )
            .scalar()
            or 0
        )
        return int(fee_sum)

    payment_time = _payment_time_expression()
    fee_sum = (
        db.query(func.coalesce(func.sum(OrderPayment.fee_cents), 0))
        .filter(
            OrderPayment.tenant_id == tenant_id,
            OrderPayment.status == "paid",
            payment_time >= start,
            payment_time <= end,
        )
        .scalar()
        or 0
    )
    return int(fee_sum)


def _fee_map_by_day(db: Session, tenant_id: int, start: datetime, end: datetime) -> dict[str, int]:
    fee_count = (
        db.query(func.count(CashMovement.id))
        .filter(
            CashMovement.tenant_id == tenant_id,
            _fee_categories_filter(),
            CashMovement.occurred_at >= start,
            CashMovement.occurred_at <= end,
        )
        .scalar()
        or 0
    )
    if fee_count:
        rows = (
            db.query(
                func.strftime("%Y-%m-%d", CashMovement.occurred_at).label("bucket"),
                func.coalesce(func.sum(CashMovement.amount_cents), 0).label("fees_cents"),
            )
            .filter(
                CashMovement.tenant_id == tenant_id,
                _fee_categories_filter(),
                CashMovement.occurred_at >= start,
                CashMovement.occurred_at <= end,
            )
            .group_by("bucket")
            .all()
        )
        return {row.bucket: int(row.fees_cents or 0) for row in rows if row.bucket}

    payment_time = _payment_time_expression()
    rows = (
        db.query(
            func.strftime("%Y-%m-%d", payment_time).label("bucket"),
            func.coalesce(func.sum(OrderPayment.fee_cents), 0).label("fees_cents"),
        )
        .filter(
            OrderPayment.tenant_id == tenant_id,
            OrderPayment.status == "paid",
            payment_time >= start,
            payment_time <= end,
        )
        .group_by("bucket")
        .all()
    )
    return {row.bucket: int(row.fees_cents or 0) for row in rows if row.bucket}


def _cogs_total(db: Session, tenant_id: int, start: datetime, end: datetime) -> tuple[int, bool]:
    movements = (
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
    if not movements:
        return 0, False

    total_cents = 0
    for movement, item in movements:
        cost_cents = int(item.cost_cents or 0)
        quantity = float(movement.quantity or 0)
        total_cents += int(round(quantity * cost_cents))

    return total_cents, True


def _granularity_format(granularity: str) -> str:
    if granularity == "day":
        return "%Y-%m-%d"
    if granularity == "week":
        return "%Y-W%W"
    if granularity == "month":
        return "%Y-%m"
    raise HTTPException(status_code=400, detail="Granularidade inválida")


def _build_timeseries(
    db: Session,
    tenant_id: int,
    start: datetime,
    end: datetime,
    granularity: str,
) -> tuple[list[dict], bool]:
    fmt = _granularity_format(granularity)
    payment_time = _payment_time_expression()

    payment_rows = (
        db.query(
            func.strftime(fmt, payment_time).label("bucket"),
            func.coalesce(func.sum(OrderPayment.amount_cents), 0).label("gross_revenue_cents"),
            func.coalesce(func.sum(OrderPayment.fee_cents), 0).label("fees_cents"),
            func.count(func.distinct(OrderPayment.order_id)).label("orders_count"),
        )
        .filter(
            OrderPayment.tenant_id == tenant_id,
            OrderPayment.status == "paid",
            payment_time >= start,
            payment_time <= end,
        )
        .group_by("bucket")
        .all()
    )

    cogs_rows = (
        db.query(
            func.strftime(fmt, InventoryMovement.created_at).label("bucket"),
            func.coalesce(
                func.sum(InventoryMovement.quantity * InventoryItem.cost_cents),
                0,
            ).label("cogs_cents"),
        )
        .join(InventoryItem, InventoryItem.id == InventoryMovement.inventory_item_id)
        .filter(
            InventoryMovement.tenant_id == tenant_id,
            InventoryMovement.type == "OUT",
            InventoryMovement.reason == "sale",
            InventoryMovement.created_at >= start,
            InventoryMovement.created_at <= end,
        )
        .group_by("bucket")
        .all()
    )

    payment_map = {
        row.bucket: {
            "gross_revenue_cents": int(row.gross_revenue_cents or 0),
            "fees_cents": int(row.fees_cents or 0),
            "orders_count": int(row.orders_count or 0),
        }
        for row in payment_rows
        if row.bucket
    }
    cogs_map = {row.bucket: int(row.cogs_cents or 0) for row in cogs_rows if row.bucket}
    cogs_available = bool(cogs_rows)

    points: list[dict] = []
    if granularity == "day":
        current = start.date()
        end_date = end.date()
        while current <= end_date:
            bucket = current.isoformat()
            payments = payment_map.get(bucket, {})
            gross = int(payments.get("gross_revenue_cents", 0))
            fees = int(payments.get("fees_cents", 0))
            net = gross - fees
            cogs = int(cogs_map.get(bucket, 0))
            points.append(
                {
                    "date": bucket,
                    "gross_revenue_cents": gross,
                    "net_revenue_cents": net,
                    "orders_count": int(payments.get("orders_count", 0)),
                    "cogs_cents": cogs,
                    "gross_profit_cents": net - cogs,
                }
            )
            current += timedelta(days=1)
        return points, cogs_available

    buckets = sorted(set(payment_map.keys()) | set(cogs_map.keys()))
    for bucket in buckets:
        payments = payment_map.get(bucket, {})
        gross = int(payments.get("gross_revenue_cents", 0))
        fees = int(payments.get("fees_cents", 0))
        net = gross - fees
        cogs = int(cogs_map.get(bucket, 0))
        points.append(
            {
                "date": bucket,
                "gross_revenue_cents": gross,
                "net_revenue_cents": net,
                "orders_count": int(payments.get("orders_count", 0)),
                "cogs_cents": cogs,
                "gross_profit_cents": net - cogs,
            }
        )

    return points, cogs_available


def _paid_orders_subquery(
    db: Session,
    tenant_id: int,
    start: datetime,
    end: datetime,
):
    payment_time = _payment_time_expression()
    return (
        db.query(OrderPayment.order_id)
        .filter(
            OrderPayment.tenant_id == tenant_id,
            OrderPayment.status == "paid",
            payment_time >= start,
            payment_time <= end,
        )
        .distinct()
        .subquery()
    )


def _order_payment_totals(
    db: Session,
    tenant_id: int,
    start: datetime,
    end: datetime,
) -> dict[int, dict[str, int]]:
    payment_time = _payment_time_expression()
    rows = (
        db.query(
            OrderPayment.order_id.label("order_id"),
            func.coalesce(func.sum(OrderPayment.amount_cents), 0).label("gross_cents"),
            func.coalesce(func.sum(OrderPayment.fee_cents), 0).label("fee_cents"),
        )
        .filter(
            OrderPayment.tenant_id == tenant_id,
            OrderPayment.status == "paid",
            payment_time >= start,
            payment_time <= end,
        )
        .group_by(OrderPayment.order_id)
        .all()
    )
    return {
        int(row.order_id): {
            "gross_cents": int(row.gross_cents or 0),
            "fee_cents": int(row.fee_cents or 0),
        }
        for row in rows
    }


def _menu_item_cost_map(db: Session, tenant_id: int, menu_item_ids: list[int]) -> dict[int, int]:
    if not menu_item_ids:
        return {}
    rows = (
        db.query(
            MenuItemIngredient.menu_item_id,
            MenuItemIngredient.quantity,
            InventoryItem.cost_cents,
        )
        .join(InventoryItem, InventoryItem.id == MenuItemIngredient.inventory_item_id)
        .filter(
            MenuItemIngredient.tenant_id == tenant_id,
            MenuItemIngredient.menu_item_id.in_(menu_item_ids),
        )
        .all()
    )
    cost_map: dict[int, int] = {}
    for row in rows:
        menu_item_id = int(row.menu_item_id)
        quantity = float(row.quantity or 0)
        cost_cents = int(row.cost_cents or 0)
        cost_map[menu_item_id] = cost_map.get(menu_item_id, 0) + int(round(quantity * cost_cents))
    return cost_map


def _allocate_fees(order_fee_cents: int, order_items_total: int) -> float:
    if order_items_total <= 0:
        return 0.0
    return float(order_fee_cents) / float(order_items_total)


def _fallback_top_items(
    tenant_id: int,
    start: datetime,
    end: datetime,
    limit: int,
    db: Session,
) -> List[Dict[str, Any]]:
    import json

    paid_orders = (
        db.query(Order)
        .join(OrderPayment, OrderPayment.order_id == Order.id)
        .filter(
            Order.tenant_id == tenant_id,
            OrderPayment.tenant_id == tenant_id,
            OrderPayment.status == "paid",
            _payment_time_expression() >= start,
            _payment_time_expression() <= end,
        )
        .distinct()
        .all()
    )
    if not paid_orders:
        return []

    payment_totals = _order_payment_totals(db, tenant_id, start, end)
    order_totals: dict[int, int] = {}
    order_items: dict[int, list[dict]] = {}

    for order in paid_orders:
        try:
            items = json.loads(order.items_json or "[]")
        except Exception:
            items = []
        if not isinstance(items, list):
            items = []
        order_items[order.id] = items
        order_totals[order.id] = 0
        for item in items:
            order_totals[order.id] += int(item.get("subtotal_cents", 0) or 0)

    totals: Dict[str, Dict[str, int]] = {}

    for order in paid_orders:
        items = order_items.get(order.id, [])
        fee_ratio = _allocate_fees(payment_totals.get(order.id, {}).get("fee_cents", 0), order_totals.get(order.id, 0))
        for item in items:
            name = str(item.get("name", "") or "").strip()
            if not name:
                continue
            qty = int(item.get("quantity", 0) or 0)
            gross_cents = int(item.get("subtotal_cents", 0) or 0)
            fee_share = int(round(gross_cents * fee_ratio)) if fee_ratio else 0
            net_cents = gross_cents - fee_share
            if name not in totals:
                totals[name] = {
                    "qty": 0,
                    "gross_revenue_cents": 0,
                    "net_revenue_cents": 0,
                }
            totals[name]["qty"] += qty
            totals[name]["gross_revenue_cents"] += gross_cents
            totals[name]["net_revenue_cents"] += net_cents

    sorted_items = sorted(
        totals.items(),
        key=lambda item: item[1]["gross_revenue_cents"],
        reverse=True,
    )
    result = []
    for name, values in sorted_items[:limit]:
        net = values["net_revenue_cents"]
        result.append(
            {
                "item_name": name,
                "qty": values["qty"],
                "gross_revenue_cents": values["gross_revenue_cents"],
                "net_revenue_cents": net,
                "cogs_cents": 0,
                "gross_profit_cents": net,
            }
        )
    return result


@router.get("/financial/summary")
def financial_summary(
    tenant_id: int = Query(...),
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator", "cashier"])),
):
    start, end = _date_range(from_date, to_date)
    payment_time = _payment_time_expression()

    gross_revenue_cents = (
        db.query(func.coalesce(func.sum(OrderPayment.amount_cents), 0))
        .filter(
            OrderPayment.tenant_id == tenant_id,
            OrderPayment.status == "paid",
            payment_time >= start,
            payment_time <= end,
        )
        .scalar()
        or 0
    )

    orders_count = (
        db.query(func.count(func.distinct(OrderPayment.order_id)))
        .filter(
            OrderPayment.tenant_id == tenant_id,
            OrderPayment.status == "paid",
            payment_time >= start,
            payment_time <= end,
        )
        .scalar()
        or 0
    )

    fees_cents = _sum_fees_cents(db, tenant_id, start, end)
    net_revenue_cents = int(gross_revenue_cents) - int(fees_cents)

    cash_in_cents = (
        db.query(func.coalesce(func.sum(CashMovement.amount_cents), 0))
        .filter(
            CashMovement.tenant_id == tenant_id,
            CashMovement.type == "in",
            CashMovement.occurred_at >= start,
            CashMovement.occurred_at <= end,
        )
        .scalar()
        or 0
    )
    cash_out_cents = (
        db.query(func.coalesce(func.sum(CashMovement.amount_cents), 0))
        .filter(
            CashMovement.tenant_id == tenant_id,
            CashMovement.type == "out",
            CashMovement.occurred_at >= start,
            CashMovement.occurred_at <= end,
        )
        .scalar()
        or 0
    )
    cash_balance_cents = int(cash_in_cents) - int(cash_out_cents)

    cogs_cents, cogs_available = _cogs_total(db, tenant_id, start, end)
    gross_profit_cents = net_revenue_cents - int(cogs_cents)
    avg_ticket_cents = int(net_revenue_cents / orders_count) if orders_count else 0

    return {
        "gross_revenue_cents": int(gross_revenue_cents),
        "fees_cents": int(fees_cents),
        "net_revenue_cents": int(net_revenue_cents),
        "cogs_cents": int(cogs_cents),
        "cogs_available": bool(cogs_available),
        "gross_profit_cents": int(gross_profit_cents),
        "orders_count": int(orders_count),
        "avg_ticket_cents": int(avg_ticket_cents),
        "cash_in_cents": int(cash_in_cents),
        "cash_out_cents": int(cash_out_cents),
        "cash_balance_cents": int(cash_balance_cents),
    }


@router.get("/sales/timeseries")
def sales_timeseries(
    tenant_id: int = Query(...),
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    granularity: str = Query("day"),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator", "cashier"])),
):
    start, end = _date_range(from_date, to_date)
    points, cogs_available = _build_timeseries(db, tenant_id, start, end, granularity)
    return {"points": points, "cogs_available": bool(cogs_available)}


@router.get("/sales/top-items")
def sales_top_items(
    tenant_id: int = Query(...),
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator", "cashier"])),
):
    start, end = _date_range(from_date, to_date)
    paid_orders = _paid_orders_subquery(db, tenant_id, start, end)

    order_items = (
        db.query(OrderItem)
        .filter(OrderItem.tenant_id == tenant_id, OrderItem.order_id.in_(paid_orders))
        .all()
    )

    if not order_items:
        items = _fallback_top_items(tenant_id=tenant_id, start=start, end=end, limit=limit, db=db)
        return {"items": items}

    payment_totals = _order_payment_totals(db, tenant_id, start, end)
    order_totals: dict[int, int] = {}
    for item in order_items:
        order_totals[item.order_id] = order_totals.get(item.order_id, 0) + int(item.subtotal_cents or 0)

    menu_item_ids = list({item.menu_item_id for item in order_items if item.menu_item_id})
    cost_map = _menu_item_cost_map(db, tenant_id, menu_item_ids)

    totals: dict[str, dict[str, int]] = {}
    for item in order_items:
        name = str(item.name or "").strip()
        if not name:
            continue
        gross_cents = int(item.subtotal_cents or 0)
        fee_ratio = _allocate_fees(
            payment_totals.get(item.order_id, {}).get("fee_cents", 0),
            order_totals.get(item.order_id, 0),
        )
        fee_share = int(round(gross_cents * fee_ratio)) if fee_ratio else 0
        net_cents = gross_cents - fee_share
        qty = int(item.quantity or 0)
        cost_per_unit = cost_map.get(int(item.menu_item_id)) if item.menu_item_id else 0
        cogs_cents = int(qty * (cost_per_unit or 0))
        if name not in totals:
            totals[name] = {
                "qty": 0,
                "gross_revenue_cents": 0,
                "net_revenue_cents": 0,
                "cogs_cents": 0,
            }
        totals[name]["qty"] += qty
        totals[name]["gross_revenue_cents"] += gross_cents
        totals[name]["net_revenue_cents"] += net_cents
        totals[name]["cogs_cents"] += cogs_cents

    sorted_items = sorted(
        totals.items(),
        key=lambda item: item[1]["gross_revenue_cents"],
        reverse=True,
    )
    results: list[dict[str, int | str]] = []
    for name, values in sorted_items[:limit]:
        net = values["net_revenue_cents"]
        cogs = values["cogs_cents"]
        results.append(
            {
                "item_name": name,
                "qty": values["qty"],
                "gross_revenue_cents": values["gross_revenue_cents"],
                "net_revenue_cents": net,
                "cogs_cents": cogs,
                "gross_profit_cents": net - cogs,
            }
        )

    return {"items": results}


@router.get("/inventory/low-stock")
def inventory_low_stock(
    tenant_id: int = Query(...),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator", "cashier"])),
):
    items = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.tenant_id == tenant_id,
            InventoryItem.active.is_(True),
            InventoryItem.current_stock < InventoryItem.min_stock_level,
        )
        .order_by(InventoryItem.name.asc())
        .all()
    )
    return {
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "current_stock": item.current_stock,
                "min_stock_level": item.min_stock_level,
                "unit": item.unit,
                "cost_cents": item.cost_cents,
            }
            for item in items
        ]
    }


@router.get("/export/financial.csv")
def export_financial_csv(
    tenant_id: int = Query(...),
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator", "cashier"])),
):
    start, end = _date_range(from_date, to_date)
    points, _ = _build_timeseries(db, tenant_id, start, end, "day")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "date",
            "gross_revenue_cents",
            "fees_cents",
            "net_revenue_cents",
            "cogs_cents",
            "gross_profit_cents",
            "orders_count",
        ]
    )

    fees_map = _fee_map_by_day(db, tenant_id, start, end)

    for point in points:
        date_key = point["date"]
        fees_cents = fees_map.get(date_key, 0)
        net_revenue_cents = int(point["gross_revenue_cents"]) - int(fees_cents)
        gross_profit_cents = net_revenue_cents - int(point["cogs_cents"])
        writer.writerow(
            [
                date_key,
                point["gross_revenue_cents"],
                fees_cents,
                net_revenue_cents,
                point["cogs_cents"],
                gross_profit_cents,
                point["orders_count"],
            ]
        )

    output.seek(0)
    headers = {"Content-Disposition": "attachment; filename=financial.csv"}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)


@router.get("/export/top-items.csv")
def export_top_items_csv(
    tenant_id: int = Query(...),
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator", "cashier"])),
):
    start, end = _date_range(from_date, to_date)
    response = sales_top_items(
        tenant_id=tenant_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        db=db,
    )
    items = response.get("items", [])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "item_name",
            "qty",
            "gross_revenue_cents",
            "net_revenue_cents",
            "cogs_cents",
            "gross_profit_cents",
        ]
    )
    for item in items:
        writer.writerow(
            [
                item.get("item_name"),
                item.get("qty"),
                item.get("gross_revenue_cents"),
                item.get("net_revenue_cents"),
                item.get("cogs_cents"),
                item.get("gross_profit_cents"),
            ]
        )

    output.seek(0)
    headers = {"Content-Disposition": "attachment; filename=top-items.csv"}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)
