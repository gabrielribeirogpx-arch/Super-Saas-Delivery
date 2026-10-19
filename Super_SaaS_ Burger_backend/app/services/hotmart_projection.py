"""Hotmart v2 DTO. Header authentication happens before parsing."""
from datetime import datetime, timezone
import re
from app.services.billing_common import BillingError

EVENTS = frozenset({"PURCHASE_APPROVED", "PURCHASE_COMPLETE", "PURCHASE_DELAYED", "PURCHASE_CANCELED",
    "PURCHASE_REFUNDED", "PURCHASE_CHARGEBACK", "SUBSCRIPTION_CANCELLATION"})
KEYS = frozenset({"id", "event", "occurred_at", "product_id", "plan_id", "subscriber_code", "transaction",
                  "approved_at", "period_end", "correlation"})

def text(value, *, required=True):
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise BillingError("invalid_hotmart_reference")
    value = str(value)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,255}", value):
        raise BillingError("invalid_hotmart_reference")
    return value

def millis(value, *, required=True):
    if value is None and not required:
        return None
    # Official contract is milliseconds. Do not guess seconds from examples.
    if type(value) is not int or value < 946684800000 or value > 7258118400000:
        raise BillingError("invalid_hotmart_timestamp")
    return datetime.fromtimestamp(value / 1000, timezone.utc)

def project(body):
    try:
        if body["version"] != "2.0.0":
            raise BillingError("unsupported_hotmart_version")
        kind = text(body["event"])
        data = body["data"]
        cancel = kind == "SUBSCRIPTION_CANCELLATION"
        sub = data.get("subscription", {})
        purchase = data.get("purchase", {})
        subscriber = data.get("subscriber", {}) if cancel else sub.get("subscriber", {})
        result = dict(id=text(body["id"]), event=kind, occurred_at=millis(body["creation_date"]).isoformat(),
            product_id=text(data["product"]["id"]), plan_id=text(sub.get("plan", {}).get("id"), required=False),
            subscriber_code=text(subscriber.get("code")), transaction=text(purchase.get("transaction"), required=False),
            approved_at=millis(purchase.get("approved_date"), required=False),
            period_end=millis(data.get("date_next_charge") if cancel else purchase.get("date_next_charge"), required=False),
            correlation=text(purchase.get("origin", {}).get("sck"), required=False))
        for key in ("approved_at", "period_end"):
            if result[key] is not None:
                result[key] = result[key].isoformat()
        if kind in {"PURCHASE_APPROVED", "PURCHASE_COMPLETE"}:
            if purchase.get("status") not in {"APPROVED", "COMPLETE"} or sub.get("status") != "ACTIVE":
                raise BillingError("hotmart_purchase_not_active_paid")
            if not all(result[key] for key in ("plan_id", "transaction", "approved_at", "period_end")):
                raise BillingError("hotmart_paid_period_missing")
        return validate_projection(result)
    except (KeyError, TypeError, AttributeError):
        raise BillingError("invalid_hotmart_payload") from None

def validate_projection(value):
    if not isinstance(value, dict) or set(value) != KEYS:
        raise BillingError("invalid_hotmart_projection")
    for key in ("id", "event", "product_id", "subscriber_code"):
        text(value[key])
    for key in ("plan_id", "transaction", "correlation"):
        text(value[key], required=False)
    for key in ("occurred_at", "approved_at", "period_end"):
        if value[key] is not None:
            try:
                date = datetime.fromisoformat(value[key])
                if date.tzinfo is None:
                    raise ValueError()
            except (TypeError, ValueError):
                raise BillingError("invalid_hotmart_projection") from None
    return dict(value)
