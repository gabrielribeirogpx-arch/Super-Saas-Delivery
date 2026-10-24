"""Bounded order history queries. Aggregates never depend on the current page."""
from datetime import date, datetime, time, timedelta, timezone
import unicodedata

from sqlalchemy import String, case, cast, func, or_
from app.models.order import Order


STATUS_GROUPS = (
    ("PENDING", "RECEBIDO"), ("CONFIRMADO", "CONFIRMED"),
    ("EM_PREPARO", "PREPARANDO", "PREPARING"),
    ("PRONTO", "READY", "READY_FOR_DELIVERY"),
    ("DRIVER_ASSIGNED", "ASSIGNED"),
    ("SAIU_PARA_ENTREGA", "OUT_FOR_DELIVERY", "IN_TRANSIT"),
    ("ENTREGUE", "DELIVERED"), ("CANCELADO", "CANCELLED"), ("FAILED",),
)


def _customer_expression(db):
    name = func.lower(func.coalesce(func.nullif(Order.customer_name, ""), Order.cliente_nome, ""))
    # Match the UI's accent-insensitive search without requiring an extension.
    accents = "áàâãäåéèêëíìîïóòôõöúùûüçñ"
    plain = "aaaaaaeeeeiiiiooooouuuucn"
    if db.bind.dialect.name == "postgresql":
        return func.translate(name, accents, plain)
    for source, target in zip(accents, plain):
        name = func.replace(name, source, target)
    return name


def history_page(db, tenant_id, *, page=1, page_size=8, order_number="", customer="",
                 status="", payment="", delivery="", created_on: date | None = None):
    query = db.query(Order).filter(Order.tenant_id == tenant_id)
    if order_number:
        query = query.filter(or_(
            cast(func.coalesce(Order.daily_order_number, Order.id), String).contains(order_number, autoescape=True),
            cast(Order.id, String).contains(order_number, autoescape=True),
        ))
    if customer:
        folded = "".join(c for c in unicodedata.normalize("NFD", customer.lower())
                         if not unicodedata.combining(c))
        query = query.filter(_customer_expression(db).contains(folded, autoescape=True))
    if status:
        key = status.upper()
        statuses = next((group for group in STATUS_GROUPS if key in group), (key,))
        query = query.filter(func.upper(Order.status).in_(statuses))
    if payment:
        query = query.filter(Order.forma_pagamento == payment)
    if delivery:
        query = query.filter(func.coalesce(func.nullif(Order.tipo_entrega, ""), cast(Order.order_type, String)) == delivery)
    if created_on:
        start = datetime.combine(created_on, time.min, tzinfo=timezone.utc)
        query = query.filter(Order.created_at >= start, Order.created_at < start + timedelta(days=1))
    total = query.count()
    rows = query.order_by(Order.created_at.desc(), Order.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return rows, total


def history_overview(db, tenant_id, *, today: date, utc_offset_minutes=0):
    # JS getTimezoneOffset is UTC minus browser local time. Preserve the existing
    # dashboard's local-day definition, explicitly independent of DB timezone.
    start = datetime.combine(today, time.min, tzinfo=timezone.utc) + timedelta(minutes=utc_offset_minutes)
    status = func.upper(Order.status)
    def count_when(condition):
        return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)
    row = db.query(
        func.count(Order.id),
        count_when((Order.created_at >= start) & (Order.created_at < start + timedelta(days=1))),
        count_when(status.in_(("PENDING", "RECEBIDO"))),
        count_when(status.in_(("EM_PREPARO", "PREPARANDO", "PREPARING"))),
        count_when(status.in_(("DRIVER_ASSIGNED", "ASSIGNED", "SAIU_PARA_ENTREGA", "OUT_FOR_DELIVERY", "IN_TRANSIT"))),
        count_when(status.in_(("ENTREGUE", "DELIVERED"))),
    ).filter(Order.tenant_id == tenant_id).one()
    payments = [value for value, in db.query(Order.forma_pagamento).filter(
        Order.tenant_id == tenant_id, Order.forma_pagamento != "").distinct().order_by(Order.forma_pagamento)]
    delivery = func.coalesce(func.nullif(Order.tipo_entrega, ""), cast(Order.order_type, String))
    deliveries = [value for value, in db.query(delivery).filter(
        Order.tenant_id == tenant_id, delivery.is_not(None), delivery != "").distinct().order_by(delivery)]
    return {"total": row[0], "summary": dict(zip(("today", "pending", "preparing", "delivering", "completed"), row[1:])),
            "payments": payments, "deliveries": deliveries}
