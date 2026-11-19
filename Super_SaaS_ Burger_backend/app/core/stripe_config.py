"""Stripe Billing configuration for new Fomizero subscriptions."""
from dataclasses import dataclass, field
import json
import os
import re

from app.services.billing_common import BillingError
from app.core.config import IS_PROD


@dataclass(frozen=True)
class StripeOffer:
    plan_code: str
    price_id: str
    price_cents: int


@dataclass(frozen=True)
class StripeSettings:
    enabled: bool = False
    environment: str = "sandbox"
    account_id: str = ""
    publishable_key: str = ""
    secret_key: str = field(default="", repr=False)
    webhook_secret: str = field(default="", repr=False)
    offers: tuple[StripeOffer, ...] = ()

    def validate(self):
        if not self.enabled:
            return
        prefix = "test" if self.environment == "sandbox" else "live"
        if (self.environment not in {"sandbox", "production"}
            or IS_PROD and self.environment != "production"
            or not re.fullmatch(r"acct_[A-Za-z0-9]+", self.account_id)
            or not self.publishable_key.startswith(f"pk_{prefix}_")
            or not self.secret_key.startswith(f"sk_{prefix}_")
            or not self.webhook_secret.startswith("whsec_")
            or len(self.webhook_secret) < 20):
            raise BillingError("incomplete_stripe_configuration")
        codes, prices = set(), set()
        if not self.offers:
            raise BillingError("stripe_offers_missing")
        for offer in self.offers:
            if (not re.fullmatch(r"[a-z][a-z0-9_]{0,49}", offer.plan_code)
                or not re.fullmatch(r"price_[A-Za-z0-9]+", offer.price_id)
                or type(offer.price_cents) is not int or offer.price_cents <= 0
                or offer.plan_code in codes or offer.price_id in prices):
                raise BillingError("invalid_stripe_offer_configuration")
            codes.add(offer.plan_code)
            prices.add(offer.price_id)


def stripe_settings() -> StripeSettings:
    enabled = os.getenv("STRIPE_BILLING_ENABLED", "false").lower() == "true"
    offers = ()
    if enabled:
        try:
            raw = json.loads(os.getenv("STRIPE_OFFERS_JSON", "[]"))
            if not isinstance(raw, list):
                raise ValueError()
            offers = tuple(StripeOffer(**item) for item in raw)
        except (TypeError, ValueError, KeyError):
            raise BillingError("invalid_stripe_offer_configuration") from None
    value = StripeSettings(enabled, os.getenv("STRIPE_ENVIRONMENT", "sandbox"),
        os.getenv("STRIPE_ACCOUNT_ID", ""), os.getenv("STRIPE_PUBLISHABLE_KEY", ""),
        os.getenv("STRIPE_SECRET_KEY", ""), os.getenv("STRIPE_WEBHOOK_SECRET", ""), offers)
    value.validate()
    return value
