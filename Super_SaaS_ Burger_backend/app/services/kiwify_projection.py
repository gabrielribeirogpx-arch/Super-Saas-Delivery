"""Only confirmed identifiers/aware timestamps, never credentials or PII."""
from datetime import datetime
import hashlib
import json
import re
from uuid import UUID

from app.services.billing_common import BillingError

FIELDS = {"order_id", "subscription_id", "product_id", "plan_id", "webhook_event_type",
          "created_at", "updated_at", "approved_date", "refunded_at", "start_date", "next_payment"}


def external_id(value):
    if not isinstance(value, str):
        raise BillingError("invalid_external_id")
    try:
        UUID(value)
    except ValueError:
        raise BillingError("invalid_external_id") from None
    if len(value) != 36:
        raise BillingError("invalid_external_id")
    return value


def validate_projection(projection):
    if not isinstance(projection, dict) or set(projection) - FIELDS:
        raise BillingError("invalid_sanitized_projection")
    for name, value in projection.items():
        if name in {"order_id", "subscription_id", "product_id", "plan_id"}:
            external_id(value)
        elif name == "webhook_event_type":
            if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z_]{0,99}", value):
                raise BillingError("invalid_event_type")
        else:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    raise ValueError()
            except (ValueError, TypeError, AttributeError):
                raise BillingError("invalid_timestamp") from None
    return projection


def project_webhook(payload):
    if not isinstance(payload, dict):
        raise BillingError("invalid_payload")
    product, subscription = payload.get("Product") or {}, payload.get("Subscription") or {}
    if not isinstance(product, dict) or not isinstance(subscription, dict):
        raise BillingError("invalid_payload")
    plan = subscription.get("plan") or {}
    if not isinstance(plan, dict):
        raise BillingError("invalid_payload")
    projection = {"order_id": payload.get("order_id"), "webhook_event_type": payload.get("webhook_event_type")}
    for field, value in (("product_id", product.get("product_id")), ("subscription_id", payload.get("subscription_id")),
                         ("plan_id", plan.get("id"))):
        if value is not None:
            projection[field] = value
    if subscription.get("id") is not None and subscription["id"] != payload.get("subscription_id"):
        raise BillingError("subscription_reference_mismatch")
    for field in ("created_at", "updated_at", "approved_date", "refunded_at", "start_date", "next_payment"):
        value = subscription.get(field) if field in {"start_date", "next_payment"} else payload.get(field)
        if isinstance(value, str):
            try:
                if datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None:
                    projection[field] = value
            except ValueError:
                pass
    validate_projection(projection)
    identity = json.dumps(["kiwify", projection["order_id"], projection["webhook_event_type"]],
                          ensure_ascii=False, separators=(",", ":")).encode()
    return projection, hashlib.sha256(identity).hexdigest()
