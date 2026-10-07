"""Official read-only sales API. No undocumented subscription routes/fields."""
from dataclasses import dataclass, field
from datetime import datetime
import time
from typing import Callable
from urllib.parse import quote

import httpx

from app.models.billing_event import BillingVerificationStatus as Verification
from app.models.subscription import SubscriptionStatus


class VerificationUnavailable(Exception):
    pass


class VerificationThrottled(VerificationUnavailable):
    """Local budget wait is not a failed provider verification attempt."""


@dataclass(frozen=True)
class VerifiedSubscription:
    """Contract for future authenticated subscription evidence, NOT a webhook DTO.

    Only a trusted source implementation may produce this. Current documented
    sales API cannot produce it. Never construct it from the incoming body.
    """
    account_id: str
    environment: str
    sale_id: str
    subscription_id: str
    product_id: str
    plan_id: str
    status: SubscriptionStatus
    period_start: datetime
    period_end: datetime
    observed_at: datetime


@dataclass(frozen=True)
class VerificationOutcome:
    status: Verification
    code: str
    subscription: VerifiedSubscription | None = field(default=None, repr=False)


class KiwifySalesAPI:
    BASE = "https://public-api.kiwify.com/v1"

    def __init__(self, settings, *, reserve: Callable[[], None], transport=None):
        self.settings = settings
        self.reserve = reserve
        self._client = httpx.Client(timeout=10, follow_redirects=False, transport=transport)
        self._token = None
        self._expires = 0

    def close(self):
        self._client.close()

    def _request(self, method, path, **kwargs):
        try:
            with self._client.stream(method, self.BASE + path, **kwargs) as response:
                if response.status_code in {404, 408, 429} or response.status_code >= 500:
                    raise VerificationUnavailable("kiwify_temporarily_unavailable")
                if response.status_code != 200:
                    return None
                chunks, total = [], 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > 512 * 1024:
                        return None
                    chunks.append(chunk)
                import json
                data = json.loads(b"".join(chunks))
                return data if isinstance(data, dict) else None
        except (httpx.RequestError, ValueError):
            raise VerificationUnavailable("kiwify_temporarily_unavailable") from None

    def verify(self, projection):
        if not self.settings.client_id or not self.settings.client_secret:
            return VerificationOutcome(Verification.MANUAL_REVIEW, "api_credentials_unavailable")
        sale_id = projection.get("order_id")
        if not sale_id:
            return VerificationOutcome(Verification.MANUAL_REVIEW, "subscription_endpoint_unconfirmed")
        # One reservation budgets BOTH token and sales calls, without exposing
        # credentials to rate limiting or issuing traffic per untrusted request.
        self.reserve()
        if self._token is None or time.monotonic() >= self._expires:
            data = self._request("POST", "/oauth/token", data={
                "client_id": self.settings.client_id, "client_secret": self.settings.client_secret})
            if not data or data.get("token_type") != "Bearer" or "sales" not in str(data.get("scope", "")).split():
                return VerificationOutcome(Verification.MANUAL_REVIEW, "api_credentials_or_scope_invalid")
            token = data.get("access_token")
            try:
                ttl = int(data["expires_in"])
            except (ValueError, KeyError, TypeError):
                ttl = 0
            if not isinstance(token, str) or not token or ttl <= 0:
                return VerificationOutcome(Verification.MANUAL_REVIEW, "api_token_response_invalid")
            self._token, self._expires = token, time.monotonic() + max(0, ttl - 60)
        data = self._request("GET", "/sales/" + quote(sale_id, safe=""), headers={
            "Authorization": "Bearer " + self._token, "x-kiwify-account-id": self.settings.account_id})
        if data is None:
            self._token = None
            return VerificationOutcome(Verification.MANUAL_REVIEW, "api_sale_response_invalid")
        product = data.get("product")
        if not isinstance(product, dict) or not isinstance(data.get("id"), str) or not isinstance(product.get("id"), str):
            return VerificationOutcome(Verification.MANUAL_REVIEW, "api_sale_response_incomplete")
        if data["id"] != sale_id or (projection.get("product_id") and product["id"] != projection["product_id"]):
            return VerificationOutcome(Verification.REJECTED, "api_sale_reference_mismatch")
        # Deliberately ignore undocumented additions named subscription/plan.
        # paid is a sale status, not proof of its subscription or access period.
        return VerificationOutcome(Verification.MANUAL_REVIEW, "sale_confirmed_subscription_unconfirmed")
