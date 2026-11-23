"""Customer-scoped MCP reads authorized by a verified Wazza identity."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.customer_points import CustomerPoints
from app.models.delivery_tracking import DeliveryTracking
from app.models.order import Order
from app.models.tenant import Tenant
from app.services.order_events import _build_tracking_url
from app.services.order_statuses import canonical_status
from app.services.plan_access import feature_allowed
from app.services.wazza_mcp_identity import VerifiedCustomerIdentity


OUT_FOR_DELIVERY_STATUSES = {"SAIU_PARA_ENTREGA"}
STATUS_LABELS = {
    "RECEBIDO": "Pedido recebido",
    "CONFIRMADO": "Pedido confirmado",
    "EM_PREPARO": "Em preparo",
    "PRONTO": "Pronto",
    "DRIVER_ASSIGNED": "Entregador atribuído",
    "SAIU_PARA_ENTREGA": "Saiu para entrega",
    "ENTREGUE": "Entregue",
    "CANCELADO": "Cancelado",
    "CANCELLED": "Cancelado",
    "CANCELED": "Cancelado",
    "FAILED": "Não concluído",
}


class EmptyCustomerArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecentOrdersArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=10, ge=1, le=20)


class CustomerOrderArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: int = Field(gt=0)


def _phone_variants(phone: str) -> set[str]:
    digits = "".join(character for character in str(phone or "") if character.isdigit())
    variants = {digits, f"+{digits}"}
    if digits.startswith("55") and len(digits) in (12, 13):
        variants.add(digits[2:])
    return {value for value in variants if value}


def _mask_phone(phone: str) -> str:
    digits = "".join(character for character in phone if character.isdigit())
    return f"+{digits[:2]}******{digits[-2:]}" if len(digits) >= 4 else "***"


def _mask_email(email: str | None) -> str | None:
    value = str(email or "").strip().lower()
    if "@" not in value:
        return None
    name, domain = value.split("@", 1)
    return f"{name[:1]}***@{domain}" if name and domain else None


def _customer_rows(
    db: Session,
    tenant_id: int,
    identity: VerifiedCustomerIdentity,
) -> list[Customer]:
    variants = _phone_variants(identity.phone)
    return (
        db.query(Customer)
        .filter(
            Customer.tenant_id == tenant_id,
            Customer.is_active.is_(True),
            or_(Customer.phone_normalized.in_(variants), Customer.phone.in_(variants)),
        )
        .order_by(Customer.updated_at.desc(), Customer.id.desc())
        .all()
    )


def _customer_ids(db: Session, tenant_id: int, identity: VerifiedCustomerIdentity) -> list[int]:
    return [int(customer.id) for customer in _customer_rows(db, tenant_id, identity)]


def _owned_orders_query(db: Session, tenant_id: int, identity: VerifiedCustomerIdentity):
    variants = _phone_variants(identity.phone)
    customer_ids = _customer_ids(db, tenant_id, identity)
    ownership = or_(
        Order.customer_id.in_(customer_ids),
        and_(
            Order.customer_id.is_(None),
            or_(Order.customer_phone.in_(variants), Order.cliente_telefone.in_(variants)),
        ),
    )
    return db.query(Order).filter(Order.tenant_id == tenant_id, ownership)


def _status_data(order: Order) -> dict[str, Any]:
    status = canonical_status(order.status)
    return {
        "order_id": int(order.id),
        "order_number": int(order.daily_order_number or order.id),
        "status": status,
        "status_label": STATUS_LABELS.get(status, "Status em atualização"),
        "total_cents": int(order.total_cents if order.total_cents is not None else order.valor_total or 0),
        "payment_method": order.payment_method or order.forma_pagamento or None,
        "delivery_type": order.order_type or order.tipo_entrega or None,
        "created_at": order.created_at.isoformat() if isinstance(order.created_at, datetime) else None,
    }


def _is_delivery_order(order: Order) -> bool:
    order_type = str(order.order_type or "").strip().lower()
    legacy_type = str(order.tipo_entrega or "").strip().upper()
    return order_type == "delivery" and legacy_type not in {
        "RETIRADA",
        "PICKUP",
        "MESA",
        "TABLE",
    }


def _owned_order(
    db: Session,
    tenant_id: int,
    identity: VerifiedCustomerIdentity,
    order_id: int,
) -> Order | None:
    return _owned_orders_query(db, tenant_id, identity).filter(Order.id == order_id).first()


def customer_get_profile(
    db: Session,
    tenant_id: int,
    _args: EmptyCustomerArguments,
    identity: VerifiedCustomerIdentity,
) -> dict[str, Any]:
    customers = _customer_rows(db, tenant_id, identity)
    customer = customers[0] if customers else None
    return {
        "customer": {
            "registered": customer is not None,
            "name": (customer.name or None) if customer else None,
            "phone_masked": _mask_phone(identity.phone),
            "email_masked": _mask_email(customer.email) if customer else None,
            "member_since": customer.created_at.isoformat() if customer and customer.created_at else None,
        }
    }


def customer_get_points(
    db: Session,
    tenant_id: int,
    _args: EmptyCustomerArguments,
    identity: VerifiedCustomerIdentity,
) -> dict[str, Any]:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    enabled = bool(tenant and tenant.points_enabled and feature_allowed(db, tenant_id, "loyalty"))
    customer_ids = _customer_ids(db, tenant_id, identity)
    rows = (
        db.query(CustomerPoints)
        .filter(CustomerPoints.tenant_id == tenant_id, CustomerPoints.customer_id.in_(customer_ids))
        .all()
        if enabled and customer_ids
        else []
    )
    return {
        "loyalty": {
            "enabled": enabled,
            "available_points": sum(int(row.available_points or 0) for row in rows),
            "lifetime_points": sum(int(row.lifetime_points or 0) for row in rows),
        }
    }


def order_list_recent(
    db: Session,
    tenant_id: int,
    args: RecentOrdersArguments,
    identity: VerifiedCustomerIdentity,
) -> dict[str, Any]:
    rows = (
        _owned_orders_query(db, tenant_id, identity)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(args.limit)
        .all()
    )
    return {"orders": [_status_data(order) for order in rows]}


def order_get_status(
    db: Session,
    tenant_id: int,
    args: CustomerOrderArguments,
    identity: VerifiedCustomerIdentity,
) -> dict[str, Any]:
    order = _owned_order(db, tenant_id, identity, args.order_id)
    return {"found": order is not None, "order": _status_data(order) if order else None}


def order_get_tracking(
    db: Session,
    tenant_id: int,
    args: CustomerOrderArguments,
    identity: VerifiedCustomerIdentity,
) -> dict[str, Any]:
    order = _owned_order(db, tenant_id, identity, args.order_id)
    if order is None:
        return {"found": False, "tracking": None}
    status = canonical_status(order.status)
    eligible = (
        status in OUT_FOR_DELIVERY_STATUSES
        and _is_delivery_order(order)
        and order.assigned_delivery_user_id is not None
        and feature_allowed(db, tenant_id, "tracking")
    )
    tracking_url = _build_tracking_url(order) if eligible else None
    tracking = (
        db.query(DeliveryTracking)
        .filter(DeliveryTracking.order_id == order.id)
        .order_by(DeliveryTracking.created_at.desc(), DeliveryTracking.id.desc())
        .first()
        if tracking_url
        else None
    )
    return {
        "found": True,
        "tracking": {
            "available": bool(tracking_url),
            "status": status,
            "status_label": STATUS_LABELS.get(status, "Status em atualização"),
            "tracking_url": tracking_url,
            "remaining_seconds": int(tracking.route_duration_seconds) if tracking and tracking.route_duration_seconds is not None else None,
            "distance_meters": int(tracking.route_distance_meters) if tracking and tracking.route_distance_meters is not None else None,
            "updated_at": tracking.created_at.isoformat() if tracking and tracking.created_at else None,
        },
    }


CUSTOMER_TOOL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "customer_get_profile": {
        "title": "Consultar perfil do cliente",
        "description": "Retorna dados mínimos da conta vinculada ao WhatsApp autenticado.",
        "scope": "customer:read",
        "arguments_model": EmptyCustomerArguments,
        "handler": customer_get_profile,
        "requires_customer": True,
    },
    "customer_get_points": {
        "title": "Consultar pontos do cliente",
        "description": "Retorna saldo e total histórico de pontos do WhatsApp autenticado.",
        "scope": "customer:read",
        "arguments_model": EmptyCustomerArguments,
        "handler": customer_get_points,
        "requires_customer": True,
    },
    "order_list_recent": {
        "title": "Listar pedidos recentes do cliente",
        "description": "Lista pedidos recentes pertencentes ao WhatsApp autenticado.",
        "scope": "order:read",
        "arguments_model": RecentOrdersArguments,
        "handler": order_list_recent,
        "requires_customer": True,
    },
    "order_get_status": {
        "title": "Consultar status de pedido",
        "description": "Consulta um pedido somente quando ele pertence ao WhatsApp autenticado.",
        "scope": "order:read",
        "arguments_model": CustomerOrderArguments,
        "handler": order_get_status,
        "requires_customer": True,
    },
    "order_get_tracking": {
        "title": "Consultar rastreamento de pedido",
        "description": "Retorna rastreamento apenas para uma entrega própria atualmente em rota.",
        "scope": "order:read",
        "arguments_model": CustomerOrderArguments,
        "handler": order_get_tracking,
        "requires_customer": True,
    },
}
