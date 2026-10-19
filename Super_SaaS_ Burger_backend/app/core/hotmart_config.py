"""Explicit Hotmart configuration; no production checkout enabled by default."""
from dataclasses import dataclass, field
import json
import os
import re
from urllib.parse import urlsplit, parse_qs
from app.services.billing_common import BillingError

WEBHOOK_PATH = "/api/webhooks/billing/hotmart"

@dataclass(frozen=True)
class HotmartOffer:
    plan_code: str
    product_id: str
    plan_id: str
    checkout_url: str
    price_cents: int

@dataclass(frozen=True)
class HotmartSettings:
    enabled: bool = False
    environment: str = "sandbox"
    account_id: str = ""
    hottok: str = field(default="", repr=False)
    client_id: str = field(default="", repr=False)
    client_secret: str = field(default="", repr=False)
    basic: str = field(default="", repr=False)
    offers: tuple[HotmartOffer, ...] = ()

    def validate(self):
        if not self.enabled:
            return
        if self.environment not in {"sandbox", "production"} or not self.account_id or len(self.hottok) < 16:
            raise BillingError("incomplete_hotmart_configuration")
        if not all((self.client_id, self.client_secret, self.basic)):
            raise BillingError("incomplete_hotmart_api_credentials")
        if self.environment == "sandbox" and os.getenv("ENV", "").lower() == "production":
            raise BillingError("hotmart_sandbox_in_production")
        codes, bindings = set(), set()
        for offer in self.offers:
            if not all(isinstance(v,str) for v in (offer.plan_code,offer.product_id,offer.plan_id,offer.checkout_url)):
                raise BillingError("invalid_hotmart_offer_configuration")
            parts = urlsplit(offer.checkout_url)
            if (not re.fullmatch(r"[a-z][a-z0-9_]{0,49}", offer.plan_code)
                or not offer.product_id.isdigit() or not offer.plan_id.isdigit()
                or type(offer.price_cents) is not int or offer.price_cents <= 0
                or parts.scheme != "https" or parts.netloc != "pay.hotmart.com"
                or not re.fullmatch(r"/[A-Za-z0-9]+", parts.path) or parts.fragment
                or any(k not in {"off", "checkoutMode"} for k in parse_qs(parts.query, keep_blank_values=True))
                or any(len(v) != 1 for v in parse_qs(parts.query,keep_blank_values=True).values())
                or offer.plan_code in codes or (offer.product_id, offer.plan_id) in bindings):
                raise BillingError("invalid_hotmart_offer_configuration")
            codes.add(offer.plan_code)
            bindings.add((offer.product_id, offer.plan_id))
        if not self.offers:
            raise BillingError("hotmart_offers_missing")


def hotmart_settings():
    enabled = os.getenv("HOTMART_BILLING_ENABLED", "false").lower() == "true"
    offers = ()
    if enabled:
        try:
            raw = json.loads(os.getenv("HOTMART_OFFERS_JSON", "[]"))
            if not isinstance(raw, list):
                raise ValueError()
            offers = tuple(HotmartOffer(**item) for item in raw)
        except (TypeError, ValueError):
            raise BillingError("invalid_hotmart_offer_configuration") from None
    value = HotmartSettings(enabled, os.getenv("HOTMART_ENVIRONMENT", "sandbox"),
        os.getenv("HOTMART_ACCOUNT_ID", ""), os.getenv("HOTMART_HOTTOK", ""),
        os.getenv("HOTMART_CLIENT_ID", ""), os.getenv("HOTMART_CLIENT_SECRET", ""),
        os.getenv("HOTMART_BASIC", ""), offers)
    value.validate()
    return value
